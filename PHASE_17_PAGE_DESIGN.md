# Phase 17.0 Page Design & Visual Layout

## The Core Idea

**One web page. Three things on it:**
1. A big voice button (Gemini Live) at the top
2. A chat area in the middle (you see Gemini's questions, you speak/type answers)
3. An auto-generated GitHub Issue preview on the right side (updates as you talk)

**Goal:** User lands on page → clicks voice button → has a natural conversation → issue auto-builds → clicks "File to investisor" → done.

---

## My Recommendation: Option B (Full-Width Chat + Collapsible Preview)

**Why this one?**
- Works great on mobile (stacks naturally)
- Keeps focus on the conversation (not split attention)
- Preview doesn't feel intrusive
- Simplest to build
- Aligns with how Chat apps (ChatGPT, Claude.ai) work — familiar pattern

---

## Visual Layout (Desktop)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Dark Factory – Feature Intake                              [? Help] [×]   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                                                                     │  │
│  │                                                                     │  │
│  │                    🎤 START VOICE CONVERSATION                     │  │
│  │                                                                     │  │
│  │           Describe your feature idea. Speak naturally.             │  │
│  │                   I'll ask clarifying questions.                   │  │
│  │                                                                     │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ─────────────────────────────────────────────────────────────────────    │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Conversation will appear here...                                   │  │
│  │                                                                     │  │
│  │                                                                     │  │
│  │ [User message (right, blue)]          14:23                        │  │
│  │ I need a way to bulk process PDFs                                  │  │
│  │                                                                     │  │
│  │ [AI response (left, gray)]             14:24                       │  │
│  │ Interesting! What does "process" mean? Are you extracting text,   │  │
│  │ searching, summarizing, or something else?                         │  │
│  │                                                                     │  │
│  │ [User message]                         14:25                       │  │
│  │ Extract text and keep the formatting                               │  │
│  │                                                                     │  │
│  │ [AI response]                          14:26                       │  │
│  │ Got it — preserve layout, bold, tables, etc. How many PDFs at once?│  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ [🎤 Recording... ] "Probably hundreds..."                          │  │
│  │                                                                     │  │
│  │ or                                                                  │  │
│  │                                                                     │  │
│  │ [Input box] Type your answer... [Send →]                          │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ▼ Issue Preview (click to expand/collapse)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │📋 GitHub Issue Draft                                              │  │
│  │                                                                     │  │
│  │ Title: Bulk PDF text extraction with formatting preservation      │  │
│  │                                                                     │  │
│  │ Description:                                                       │  │
│  │ User needs to process batches of PDF documents (100+ at a time),   │  │
│  │ extracting text while preserving formatting (bold, italics,       │  │
│  │ tables). Primary file types: PDF, possibly Word docs too.         │  │
│  │                                                                     │  │
│  │ Acceptance Criteria:                                               │  │
│  │ ☐ Accepts PDF files (batch upload)                                │  │
│  │ ☐ Preserves text formatting (bold, italics, tables)               │  │
│  │ ☐ Handles 100+ files without timeout                              │  │
│  │ ☐ Error handling for corrupted PDFs                               │  │
│  │ ☐ Returns extracted text in structured format                     │  │
│  │                                                                     │  │
│  │ Labels: enhancement, bulk-processing, pdf                         │  │
│  │ Priority: medium (inferred)                                        │  │
│  │                                                                     │  │
│  │ [✏️ Edit] [File Issue to investisor →] [Save Draft]              │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Layout Breakdown

### Header (Fixed at Top)
```
Dark Factory – Feature Intake    [? Help] [×]
```
- Left: Logo + title (maybe tiny Dark Factory icon)
- Right: Help link (explains "How does this work?"), Close button (for later when multiple windows exist)

---

### Hero Section (Before Conversation Starts)
```
         🎤 START VOICE CONVERSATION

  Describe your feature idea. Speak naturally.
        I'll ask clarifying questions.
```
- Large button (120px diameter, centered)
- Animated mic icon (subtle pulse when idle, grows on hover)
- Explanatory text below (small, gray)
- **Alternative button below (or in menu):** "Or type your idea" (for accessibility, or if user prefers text)

---

### Conversation Area (Main Content)
- Full-width chat history
- **User messages (right-aligned):**
  - Blue bubble (or accent color)
  - Timestamp on right
  - Text left-aligned inside bubble
  
- **AI messages (left-aligned):**
  - Gray bubble (#f0f0f0 or similar)
  - Timestamp on left
  - Text left-aligned
  - Animated "..." while generating

- **System messages (center, subtle):**
  - "Conversation saved to draft"
  - "Switching to voice recognition..."

---

### Input Area (Bottom of Chat)
**Two modes:**

**Mode 1: Voice is active**
```
[🎤 Recording... 2:34s elapsed ] "Your voice input transcribed here..."

[Stop] [Clear & Retry]
```

**Mode 2: Text fallback (or after voice ends)**
```
[Type your answer or press 🎤 to speak...                        ] [Send →]
```

---

### Issue Preview Section (Collapsible)
```
▼ Issue Preview (click to collapse)

📋 Title: Bulk PDF text extraction...

Description: [multi-line text]

Acceptance Criteria:
☐ Accepts PDF files...
☐ Preserves formatting...

Labels: enhancement, bulk-processing
Priority: medium

[✏️ Edit Fields] [📤 File Issue] [💾 Save Draft] [🔄 Start Over]
```

**Why collapsible?**
- Not intrusive during conversation
- User can focus on speaking/typing
- Expands when they want to review before filing
- Stays open once expanded

---

## Visual Style (Proposed)

### Colors
```
Background: #ffffff (light) or #1a1a1a (dark mode)
Text: #000000 (light) or #e0e0e0 (dark)
User Message Bubble: #0066cc (blue)
AI Message Bubble: #f5f5f5 (light) or #2a2a2a (dark)
Buttons: #0066cc (primary), #ff6b6b (secondary/danger)
Accent: #10b981 (green for success/file action)
```

### Typography
```
Header: 24px, bold, sans-serif
Button Text: 16px, bold
Chat Text: 14px, regular
Timestamps: 12px, gray, regular
Labels: 12px, bold, small caps
```

### Spacing
```
Page padding: 16px (mobile), 24px (desktop)
Chat bubble margins: 12px vertical between messages
Button padding: 12px 24px
Input field height: 48px (easy touch target)
```

### Animations
```
Voice button hover: scale 1.05, shadow grows
Message entrance: fade-in 300ms
Typing indicator (...): pulse animation
Success feedback: green checkmark, 2s fade-out
```

---

## Mobile View (Phone, <640px)

```
┌──────────────────────────────────────────┐
│  Dark Factory     [? Help] [×]           │
├──────────────────────────────────────────┤
│                                          │
│              🎤 START VOICE              │
│          Speak your feature idea         │
│                                          │
│  ─────────────────────────────────────   │
│                                          │
│  [User] I need bulk PDF processing       │
│  [AI]   What do you mean by "process"?   │
│  [User] Extract text, keep formatting    │
│                                          │
│  ─────────────────────────────────────   │
│                                          │
│  [🎤 Recording... 1:23s]                │
│                                          │
│  ─────────────────────────────────────   │
│                                          │
│  ▼ Issue Preview                         │
│  ┌────────────────────────────────────┐ │
│  │ 📋 Bulk PDF Processing             │ │
│  │                                    │ │
│  │ Extract text, preserve formatting, │ │
│  │ handle 100+ files...               │ │
│  │                                    │ │
│  │ ☐ Batch upload                    │ │
│  │ ☐ Format preservation              │ │
│  │ ☐ Handle 100+ files                │ │
│  │                                    │ │
│  │ [File Issue] [Save Draft]           │ │
│  └────────────────────────────────────┘ │
│                                          │
└──────────────────────────────────────────┘
```

**Mobile adaptations:**
- Stacked vertically (no side-by-side)
- Buttons full-width
- Chat text slightly smaller (12px)
- Collapsible sections to save space
- Touch targets: min 48px (finger-friendly)

---

## User Interaction: Step-by-Step Flow

### Step 1: Land on Page
- User sees hero section with big voice button
- Conversation area is empty
- Issue preview is collapsed/hidden

### Step 2: Click Voice Button
- Browser requests microphone permission
- Button changes to "🎤 Recording..."
- User sees animated indicator
- Gemini Live connection established (Worker mints ephemeral token)

### Step 3: User Speaks
- "I need to bulk-process PDFs to extract text"
- Transcription appears in input area as user speaks
- When user pauses, transcript finishes and gets added as a chat bubble (user message, right-aligned)

### Step 4: AI Responds
- Gemini response comes back streamed from Worker
- Appears as AI message (left-aligned, gray bubble)
- Question: "What format should the output be?"

### Step 5: User Responds (Continues Conversation)
- User clicks 🎤 again or types answer
- Conversation goes back and forth (~8-10 exchanges)

### Step 6: AI Suggests Summary
- "I think I have enough info. Let me draft your issue:"
- System automatically expands Issue Preview
- Shows auto-generated title, description, acceptance criteria

### Step 7: User Reviews
- Can expand/collapse preview as needed
- Sees fields are editable ("Click to edit title")
- Reads acceptance criteria

### Step 8: User Files
- Clicks "📤 File Issue to investisor"
- Page shows loading state ("Creating issue...")
- Success: "✅ Issue filed! #1234 on investisor"
- Link to GitHub issue appears

### Step 9: Next Steps
- User sees options:
  - "Start another intake" (clears conversation, back to hero)
  - "View issue on GitHub"
  - "Dashboard" (to see all submitted features)

---

## Responsive Breakpoints

| Screen Size | Layout | Changes |
|------------|--------|---------|
| < 640px (mobile) | Stacked | Single column, full-width buttons, collapsible preview |
| 640–1024px (tablet) | Stacked with wider | Still vertical but more padding, larger text |
| > 1024px (desktop) | Option B (full-width chat + collapsible preview) | Chat takes full width, preview on top when expanded |

---

## Key Interaction States

### Loading States
- **Gemini thinking:** "..." animation in gray bubble
- **Filing issue:** Button shows "Creating..." with spinner
- **Voice transcribing:** Animated waveform icon in input area

### Error States
- **Mic not available:** Red banner: "Microphone not detected. Try typing instead."
- **Gemini API down:** Yellow banner: "AI currently unavailable. Manual issue filing below."
- **Network error:** Red banner with "Retry" button

### Success States
- **Issue filed:** Green checkmark, issue number/link
- **Draft saved:** Subtle green notification: "Draft saved to your browser"

---

## Summary: What This Achieves

✅ **Simple:** One page, clear entry point (big voice button)
✅ **Guided:** User doesn't get lost — AI asks questions
✅ **Fast:** Issue auto-generates, no manual form-filling
✅ **Accessible:** Text fallback always available, works on any device
✅ **Tangible:** User sees the GitHub issue building in real-time (confidence)
✅ **Natural:** Gemini Live voice is conversational, not robotic

---

## Questions for You (To Refine Further)

1. **Dark mode preferred?** Or light mode? Or toggle?

2. **Hero section:** Should there be both "Voice" and "Type" buttons side-by-side, or just voice with a fallback link for typing?

3. **Conversation history:** After filing, should past conversations be visible on a "Dashboard" page, or just deleted/cleared?

4. **Issue preview auto-expand:** Should it expand automatically once AI says "I think I have enough"? Or stay collapsed until user clicks?

5. **Success page:** After filing, should we stay on the same page with the issue link, or redirect to the investisor repo?

6. **Branding:** Any Dark Factory colors/logo I should include in the mockup?

Pick one or a few, and I'll refine the design further, then we can start building.
