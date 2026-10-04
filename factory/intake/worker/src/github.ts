/**
 * Dark Factory Intake Worker — GitHub Integration
 *
 * Handles:
 * 1. Creating new project repositories (seeded with starter template)
 * 2. Filing feature intake issues (factory:ready label, BMAD structure)
 * 3. Configuring repository secrets and labels
 *
 * Per ADR-003/ADR-005: credentials live only as Cloudflare Worker secrets,
 * never reach local processes or the browser.
 */

export interface GithubRepo {
  name: string;
  full_name: string;
  html_url: string;
  private: boolean;
  owner: string;
}

export interface GithubIssue {
  number: number;
  title: string;
  html_url: string;
}

export class GitHubIntegration {
  private token: string;
  private apiBase = "https://api.github.com";
  private owner: string;
  // GitHub's REST API hard-requires a User-Agent header and returns a 403
  // ("Request forbidden by administrative rules") without one — confirmed in
  // production via `wrangler tail` on 2026-10-04 (every fileFeatureIssue call
  // was silently failing after a successful discovery conversation).
  private static readonly USER_AGENT = "dark-factory-intake-worker";

  constructor(token: string, owner: string) {
    if (!token) {
      throw new Error("GITHUB_REPO_CREATE_TOKEN secret not configured");
    }
    this.token = token;
    this.owner = owner;
  }

  /**
   * Create a new GitHub repository for a new project idea.
   *
   * Flow:
   * 1. Create private repo with minimal seeded content
   * 2. Add factory:ready and other required labels
   * 3. Record in pending_profiles for local sync
   *
   * Seeding: either via template repo (GitHub's "generate from template" API)
   * or by pushing initial files (package.json, README, .github/workflows/deploy.yml)
   */
  async createProjectRepository(projectName: string): Promise<GithubRepo> {
    // Validate project name: alphanumeric + hyphens, no spaces/special chars
    if (!/^[a-z0-9]([a-z0-9-]{0,37}[a-z0-9])?$/.test(projectName)) {
      throw new Error(
        `Invalid project name: must be lowercase alphanumeric + hyphens, 1-39 chars (got "${projectName}")`
      );
    }

    const endpoint = `${this.apiBase}/user/repos`;

    const payload = {
      name: projectName,
      description: `Dark Factory managed project: ${projectName}`,
      private: true,
      auto_init: true, // Creates with README, LICENSE, .gitignore
      allow_squash_merge: true,
      allow_merge_commit: false, // Factory uses merge commits via git, not GitHub UI
      allow_rebase_merge: false,
      delete_branch_on_merge: true,
    };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${this.token}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": GitHubIntegration.USER_AGENT,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`GitHub API error: ${response.status} ${error}`);
      }

      const data = (await response.json()) as any;

      return {
        name: data.name,
        full_name: data.full_name,
        html_url: data.html_url,
        private: data.private,
        owner: data.owner.login,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to create repository: ${errorMsg}`);
    }
  }

  /**
   * File a feature intake issue with BMAD structure.
   *
   * Issue body includes sections that factory/analysis/bmad.py can parse:
   * - Acceptance Criteria:
   * - Non-Goals:
   * - Constraints:
   * - etc.
   *
   * Automatically adds factory:ready label so the issue is immediately eligible.
   */
  async fileFeatureIssue(
    repo: string, // "owner/name"
    title: string,
    bmadStructured: {
      description?: string;
      acceptanceCriteria?: string[];
      nonGoals?: string[];
      constraints?: string[];
      dataBehavior?: string;
      errorHandling?: string;
    }
  ): Promise<GithubIssue> {
    const endpoint = `${this.apiBase}/repos/${repo}/issues`;

    // Format the issue body with BMAD headers
    const body = this._formatBMADIssueBody(bmadStructured);

    const payload = {
      title,
      body,
      labels: ["factory:ready"],
    };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${this.token}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": GitHubIntegration.USER_AGENT,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`GitHub API error: ${response.status} ${error}`);
      }

      const data = (await response.json()) as any;

      return {
        number: data.number,
        title: data.title,
        html_url: data.html_url,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to file issue: ${errorMsg}`);
    }
  }

  /**
   * Ensure factory:ready and other required labels exist on a repository.
   */
  async ensureLabelsExist(repo: string): Promise<void> {
    const labels = [
      {
        name: "factory:ready",
        color: "00FF00",
        description: "Ready for Dark Factory to claim",
      },
      {
        name: "priority:high",
        color: "FF6600",
        description: "High priority",
      },
      {
        name: "priority:normal",
        color: "FFAA00",
        description: "Normal priority",
      },
    ];

    for (const label of labels) {
      const endpoint = `${this.apiBase}/repos/${repo}/labels`;

      try {
        await fetch(endpoint, {
          method: "POST",
          headers: {
            Accept: "application/vnd.github+json",
            Authorization: `Bearer ${this.token}`,
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": GitHubIntegration.USER_AGENT,
          },
          body: JSON.stringify({
            name: label.name,
            color: label.color,
            description: label.description,
          }),
        });
      } catch {
        // Label may already exist; suppress error
      }
    }
  }

  private _formatBMADIssueBody(
    bmad: Record<string, any>
  ): string {
    const lines: string[] = [];

    if (bmad.description) {
      lines.push(bmad.description);
      lines.push("");
    }

    if (bmad.acceptanceCriteria && bmad.acceptanceCriteria.length > 0) {
      lines.push("## Acceptance Criteria");
      lines.push("");
      for (const criterion of bmad.acceptanceCriteria) {
        lines.push(`- ${criterion}`);
      }
      lines.push("");
    }

    if (bmad.nonGoals && bmad.nonGoals.length > 0) {
      lines.push("## Non-Goals");
      lines.push("");
      for (const goal of bmad.nonGoals) {
        lines.push(`- ${goal}`);
      }
      lines.push("");
    }

    if (bmad.constraints && bmad.constraints.length > 0) {
      lines.push("## Constraints");
      lines.push("");
      for (const constraint of bmad.constraints) {
        lines.push(`- ${constraint}`);
      }
      lines.push("");
    }

    if (bmad.dataBehavior) {
      lines.push("## Data Behavior");
      lines.push("");
      lines.push(bmad.dataBehavior);
      lines.push("");
    }

    if (bmad.errorHandling) {
      lines.push("## Error Handling");
      lines.push("");
      lines.push(bmad.errorHandling);
      lines.push("");
    }

    return lines.join("\n");
  }
}

export default GitHubIntegration;
