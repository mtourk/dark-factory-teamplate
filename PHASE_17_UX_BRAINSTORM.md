# Phase 17.0 UI/UX Flow Brainstorm

## User Journey: Feature Intake via Web + Gemini Live Discovery

### Core Insight
User submits a feature idea → system clarifies via conversation → auto-generates GitHub Issue → filed to investisor.

---

## User Entry Points (Phase 17.0: Web Primary)

**Three parallel flows, web first:**

1. **Fast Text Entry** (for users who know what they want)
   - Landing page with a simple textarea: "Describe the feature you need..."
   - Click "Clarify with AI" → conversation mode

2. **Gemini Live Voice Discovery** (primary experience for Phase 17.0)
   - "Start voice conversation" button
   - Gemini Live opens → user talks freely about their idea
   - Real-time transcription + AI asking clarifying questions
   - User speaks answers back (fully conversational)
   - Ends when: user says "that's it" or AI says "I think I have enough"

3. **Gemini Live Chat** (middle ground: text chat in voice-discovery mode)
   - Same clarification flow as voice, but typed instead of spoken
   - Useful if user has accessibility needs or noisy environment

---

## The Clarification Phase (Where the Magic Happens)

**Both voice and text flow through this:**

```
User: "I need a way to bulk-process documents"

AI: "Got it. What file formats do you need to support?"

User: "PDF and Word docs, mainly."

AI: "How many documents at once? Tens? Hundreds? Thousands?"

User: "Probably hundreds at a time."

AI: "What's the processing task? Extracting text? Searching? Summarizing?"

...
(5-10 exchanges)

AI: "Okay, I think I have enough. Let me draft what I heard and you can approve it."
```

**The system is learning:**
- Feature scope
- User pain point (why they need it)
- Scale/performance expectations
- Integrations (does it need to talk to other services?)
- Priority/urgency
- Acceptance criteria (how will they know it works?)

---

## Layout Options

### Option A: Split-Screen (Two-Column)
```
┌─────────────────────┬──────────────────────┐
│   Conversation      │   Issue Preview      │
│   (Chat bubbles)    │   (Auto-updated)     │
│                     │                      │
│ User: "I need..."   │ Title: [Generated]   │
│ AI: "Format?"       │ Description: [Draft] │
│ User: "PDF..."      │ Acceptance: [...]    │
│                     │                      │
│ [Voice/Text input]  │ [Review / Approve]   │
│                     │ [File Issue]         │
└─────────────────────┴──────────────────────┘
```
**Pros:** Can see issue preview building in real-time.
**Cons:** Narrow on mobile, cognitive load (tracking two streams).

### Option B: Full-Width Chat, Collapsible Preview
```
┌──────────────────────────────────────────┐
│          Conversation Area               │
│  (Voice button at top, text input below) │
│                                          │
│ User: "Bulk process documents"           │
│ AI: "Formats needed?"                    │
│ User: "PDF, Word"                        │
│                                          │
│ [Voice input / Text input bar]           │
│                                          │
│ ▼ Issue Preview (expandable)             │
│   Title: Bulk document processing...     │
│   [Approve / Edit / File Issue]          │
└──────────────────────────────────────────┘
```
**Pros:** Mobile-friendly, less distraction until preview is needed.
**Cons:** Preview feels secondary.

### Option C: Stacked Mobile-First, Desktop Adapts
```
Mobile (stacked):
┌──────────────────────┐
│ [Voice button]       │
│ Conversation...      │
│ [Text input]         │
│ Issue Preview (sm)   │
│ [File button]        │
└──────────────────────┘

Desktop (side-by-side):
Same as Option A above
```
**Pros:** Works everywhere.
**Cons:** Design complexity.

---

## Key UI Elements & States

### 1. Voice Input Button
- **Idle:** "🎤 Start voice conversation" (large, inviting)
- **Recording:** Animated mic, real-time transcription appearing below button
- **Processing:** "Listening to Gemini... please wait"
- **Speaking (AI):** "Gemini is speaking..." (audio playing, transcript in chat)
- **Resume:** "Continue speaking" (user's turn)

### 2. Chat Message Bubbles
- **User messages:** Right-aligned, blue bubble, timestamp
- **Gemini messages:** Left-aligned, gray bubble, with "..." loader while generating
- **System messages:** Center-aligned, smaller, neutral tone (e.g., "Conversation saved to draft")

### 3. Issue Preview Box
- **Auto-updates** as conversation evolves (not manual)
- **Sections:**
  - **Title:** Auto-generated from first user statement (editable)
  - **Description:** Summary of conversation (editable)
  - **Acceptance Criteria:** Bulleted list extracted from requirements (editable)
  - **Related Models:** "Suggested Ollama model: qwen2.5-coder:32b" (if applicable)
  - **Metadata:** Priority (inferred), effort estimate (rough), labels (auto-tagged)

- **Actions:**
  - "Edit any field manually" link
  - "File Issue" button (primary, green)
  - "Save as Draft" (if user wants to think about it)
  - "Start Over" (clear conversation)

### 4. Progress Dashboard (Secondary View, Accessible from Top Nav)
- **Recent submissions:** Table of filed issues (title, timestamp, status)
  - Status: "Filed to GitHub", "Awaiting Clarification", "Draft" (not filed yet)
- **Stats:** "5 features submitted this month", "2 in review", "1 closed (implemented)"
- **Quick actions:** "View on investisor", "Chat about this issue again"

---

## Conversation Flow: What Gemini Should Ask

**Gemini's "discovery" personality:**
- Starts broad: "Tell me more about what you're trying to do."
- Narrows down: "Who's the end user? Is it engineers or business people?"
- Validates: "So you're looking for a X that does Y, right?"
- Probes depth: "What about edge cases? What if Z happens?"
- Summarizes: "Let me reflect back what I heard: ..."

**Stop conditions:**
- User says: "That's it", "I think that's enough", "Let's file it"
- AI detects: "I think I have a clear picture. Ready to turn this into an issue?"
- After ~8-10 exchanges (avoid fatigue)
- After 10 minutes (timeout, suggest: "Want to file this and continue later?")

---

## Acceptance Criteria Auto-Generation

**Gemini extracts these from the conversation:**

Example conversation:
```
User: "I need a bulk processor for PDFs."
AI: "What does 'process' mean?"
User: "Extract text from each page, keep formatting."
...
(Gemini learns: extract text, preserve formatting, handle multi-page)
```

Auto-generated acceptance criteria:
- [ ] System accepts PDF files (single or batch upload)
- [ ] Text extraction preserves page formatting (bold, italics, tables)
- [ ] Handles multi-page documents without data loss
- [ ] Processes batch of 100+ files without timeout
- [ ] Error handling for corrupted/encrypted PDFs

User can edit before filing.

---

## Phase 17.0 Specific: Gemini Live Discovery Integration

**Where does Gemini Live live?**
- **Voice endpoint:** Cloudflare Worker calls Gemini Live API
- **Ephemeral token:** Minted by the Worker (stored in Cloudflare environment, never exposed to frontend)
- **Streaming back:** WebSocket or Server-Sent Events (SSE) from Worker to web page
- **User device:** Runs a simple audio encoder (browser Web Audio API)

**Flow:**
1. User clicks "Start voice conversation"
2. Web page establishes WebSocket to Cloudflare Worker
3. Worker mints an ephemeral Gemini token (valid 1 hour)
4. Browser opens Gemini Live session via that token
5. Audio captured locally, sent to Gemini
6. Gemini responses streamed back to Worker → web page
7. Transcript + extraction saved (optional) to a "draft" database row

**Privacy note:** Audio is sent to Gemini (Google's infrastructure), not stored locally. User can choose to save/discard transcript after.

---

## Dashboard & History (Phase 17.1 Consideration)

*For now (17.0), minimal — just show current conversation.*

Later (17.1+):
- Past conversations (saved drafts)
- Filed issues (linked to GitHub)
- Gemini Live session transcripts (opt-in archive)
- Stats dashboard (velocity, issue categories)

---

## Error Handling & Edge Cases

| Scenario | Handling |
|----------|----------|
| Voice input times out | "No input detected. Try again or switch to typing." |
| Gemini API fails | "AI is currently unavailable. You can still type your idea or try again in a moment." |
| User closes mid-conversation | "Save draft?" (auto-saves for 5 min window) |
| Issue preview fails to generate | Show blank template, user fills manually |
| Network drops during filing | "Issue saved as draft. Retry filing?" |

---

## Questions for You (Pick One or More)

1. **Conversation length:** Do you want a strict ~10-message limit, or should users be able to chat as long as they want?

2. **Auto-file or manual review:** After clarification, should the system offer "File immediately" or always require user approval?

3. **Voice always, or text-first option?** Gemini Live is powerful but requires microphone access — do web page visitors need a text-only fallback that still feels primary?

4. **Visual style:** Dark mode for chat? Minimalist or colorful? Do you have a brand color palette for Dark Factory?

5. **Gemini model choice:** Gemini Live (real-time voice, ~$0 but quota-limited) vs. Gemini 2.0 Flash (cheaper, slower, text-only)? The Worker can call either.

6. **Ollama integration in Phase 17.0:** Should the Discovery AI mention "I can also run local models to analyze code samples you paste"? Or keep it Gemini-only for now?

7. **Issue destination:** Always "investisor" repo, or let users pick which repo to file to? (Affects URL/form)

Pick the ones that feel important; I'll adjust the design.
