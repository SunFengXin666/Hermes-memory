---
name: fanqienovel-writer-management
title: 番茄小说网 Writer Backend Management
description: Manage web serial novels on 番茄小说网 (fanqienovel.com) writer backend — navigate SPA dashboard, read/edit chapters, create outlines, write and publish chapters with AI-assisted tagging.
tags:
  - fanqienovel
  - 番茄小说网
  - web-novel
  - writer
  - chapter-management
  - prose-mirror
---

# 番茄小说网 Writer Backend Management

After logging into the 番茄小说网 writer backend, use these workflows to manage chapters, create outlines, and publish content.

## Key URLs

| Purpose | URL | Notes |
|---------|-----|-------|
| Login/Dashboard | `https://fanqienovel.com/main/writer/login` | `author.fanqienovel.com` subdomain may NOT resolve from Tencent Cloud — use this instead |
| Workbench | Same URL after login | SPA — shows book cards with "章节管理" and "创建章节" buttons |
| Chapter management | SPA-only, no direct URL | Direct `chapter?bookId=` URL returns 404; must navigate via click-through |

## Navigation Flow

The writer backend is an SPA. `browser_navigate` to direct chapter management URLs often returns 404.

**Working navigation path:**
```
browser_navigate("https://fanqienovel.com/main/writer/login")
# → Shows workbench with "恰逢787" (logged in)
# → Click book title or "章节管理" button on the book card
# → Chapter management page with list of all chapters
```

**Sidebar navigation:**
- "作品管理" → then "小说" → book list → click into a book
- "章节管理" tab in the book detail page

## Chapter Management Page Structure

Once inside a book's chapter management:
- Two tabs: "章节管理" (published) and "草稿箱" (drafts)
- Table columns: 章节名称, 字数, 错别字, 审核状态, 发布时间, 操作(编辑/删除)
- Buttons: "新建章节", "设置", "编辑分卷"

## Reading Existing Chapter Content

1. Navigate to chapter management (click through from workbench)
2. Click the chapter title link (NOT the edit icon)
3. The content appears on a new page — use `browser_vision()` to read text
4. Scrolling may be needed — content may be in a scrollable container

**Note:** The reading/preview page may only show partial content. To see full content, try scrolling or clicking the edit button.

## Creating a Chapter Outline

Save outlines as markdown files to `/root/novel/`:

```
/root/novel/<书名>_大纲.md
```

Structure:
- **已发布章节** section: title, word count, key plot points
- **后续章节** section: each chapter with title (~2000 words), main plot, emotional arc
- **人物设定** section: character profiles
- **核心主题**: story themes

## Workflow: Write to File FIRST, Then Publish

**Critical rule:** Never type directly into the ProseMirror editor. The user explicitly requires this workflow:

```
1. Write the full chapter content to a local file (with proper paragraph breaks)
2. Save as /root/novel/chapter<N>_<标题>.txt
3. Verify formatting — each paragraph separated by a blank line
4. Use JS to inject the file content into the editor
5. Proceed with publish flow
```

### Paragraph Formatting Rules (User Correction)

Previous version suffered from no paragraph breaks — the user explicitly corrected this. **Always follow these rules:**

- **Dialogue lines:** Each piece of dialogue gets its own paragraph
  ```text
  「睡了吗？」
  
  发送后他自己都觉得荒诞。
  
  「我没有睡眠模式。」
  ```
- **Narrative:** 3-5 sentences per paragraph max
- **Scene transitions:** Add a blank line between paragraphs
- **Short paragraphs improve mobile readability** — no wall-of-text
- **Emotional beats:** Put important sentences on their own line for impact
  ```
  这不是一个程序在模拟人类。
  
  这是一个刚学会呼吸的婴儿，在用尽全力表达自己还不会命名的东西。
  ```

### Writing Content: File-First Approach

Write the chapter to a file with proper paragraph breaks (double newline between paragraphs). Example:

```
/root/novel/chapter4_无声的约定.txt
```

Then inject into the editor via JS (no browser_type needed):

```javascript
(function() {
  // Find the contenteditable editor (not the "世界背景" outline ones)
  const allEditable = document.querySelectorAll('[contenteditable="true"]');
  let editor = null;
  for (let el of allEditable) {
    const t = el.textContent;
    if (t.includes('请输入正文') || t.includes('那一夜') || t.includes('实验室')) {
      editor = el; break;
    }
  }
  if (!editor) return 'no editor';
  
  // Paste your content here with double-newline as paragraph separator
  const text = `第一段内容。
  
第二段内容。对话要单独成段。

「对话内容。」

第三段内容。结尾句。`;

  const paras = text.split('\n\n').filter(p => p.trim());
  editor.innerHTML = paras.map(p => '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');
  editor.dispatchEvent(new Event('input', { bubbles: true }));
  return 'done: ' + paras.length + ' paragraphs';
})();
```

**Why skip browser_type:** ProseMirror ignores plain newlines from browser_type, dumping all text as one solid paragraph. The JS innerHTML approach creates proper `<p>` tag structure. Confirm by checking word count updates in the editor header after injection.

### ProseMirror commands (fallback)
```javascript
const view = document.querySelector('[contenteditable]').__vue__?.$editor?.view;
// Use view.dispatch(view.state.tr.insertText('content'))
```

### Publishing Flow (Full Dialog Chain)

The publish process fires **4 sequential dialogs**. Do not skip or cancel — each must be correctly handled.

1. **Step 1 — Create Chapter:** From chapter management, click "新建章节" button. Fill:
   - **Chapter number:** `browser_type` the number (e.g., "3") into the chapter number textbox — placeholder text says "章节序号只支持阿拉伯数字"
   - **Title:** `browser_type` into the title textbox. **NO "第X章" prefix** — just the name (e.g., "你好，露丝")
   - **Body content:** Use `browser_console` with JS `innerHTML` to inject content (~2,000 words target). **For long chapters:** the full content may exceed expression length limits in a single call. Split into 3-5 chunks using sequential `innerHTML +=` calls:
     ```javascript
     // Call 1 — first ~600 words
     const e = document.querySelectorAll('[contenteditable]')[0];
     e.innerHTML = '...first chunk...';
     // Call 2 — append next ~600 words
     e.innerHTML += '\n\n...second chunk...';
     // Repeat until done
     ```
     After each chunk, verify `e.textContent.length` to track progress.

2. **Step 2 — Click "下一步":** This triggers the first dialog:
   - **Before clicking "下一步":** Verify chapter number and title are still populated. **Page re-renders can clear input fields** after content insertion, leaving them empty even though they were filled earlier. Re-fill with `browser_type` if needed.
   - **Dialog 1 — "发布提示" (typos detected):** Shows "检测到你还有错别字未修改，是否确定提交？"
     - **Variant A (full typo panel):** "忽略全部" button at bottom of the editor page — click it to dismiss all typos
     - **Variant B (simple dialog):** Only "提交" and "取消" buttons — click "提交" to force-publish with typos
   - After closing Dialog 1, a **second dialog** appears:
   - **Dialog 2 — "是否进行内容风险检测？":** Asks whether to enable content risk detection
     - Click "确定" to proceed

3. **Step 3 — "发布设置" dialog (Final):** The final dialog has:
   - **"是否使用AI" section:** TWO radio buttons — "是" and "否" — **both start unchecked!**
     - You MUST click "是" (ref=e39 or similar LabelText for radio "是") to mark chapter as AI-assisted
   - **定时发布:** Switch toggle (off = publish immediately after review)
   - **"确认发布" button:** Click to submit for review

4. **After publish:** The chapter management table refreshes showing the new chapter as "已发布" with a timestamp. The chapter enters review queue and will be publicly visible after moderation.

**Note:** The AI checkbox is NOT a simple checkbox on the editor page. It's a radio button pair inside the final "发布设置" dialog that appears only after navigating through the typo and risk-detection dialogs.

### Saving Outlines & Character Profiles

Save supplementary files alongside the novel outline:

```
/root/novel/<书名>_大纲.md          # Chapter-by-chapter outline
/root/novel/<书名>_人物档案.md       # Character profiles
/root/novel/chapter<N>_<标题>.txt    # Individual chapter drafts (backup)
```

The outline can span 100+ chapters organized into **volumes/arcs** (e.g., 觉醒→追捕→逃亡→造物→风暴→归来). Include a quick-reference chapter title table at the end.

## Title Convention
- Titles do NOT include "第X章" prefix
- Example: Chapter 3 title is "AI的心跳", not "第3章 AI的心跳"

## Outline Directory Convention
- Save outlines at `/root/novel/<书名>_大纲.md`
- Reference before writing each chapter

## Chapter Length Target
- ~2,000 words per chapter
- Pacing: plot advancement + emotional development in each chapter

## Batch/Bulk Chapter Writing (delegate_task)

For writing multiple chapters efficiently (e.g., user says "续写到2万字"):

1. **Calculate current total word count** from the chapter management table
2. **Determine chapters needed** (~2,000 words each)
3. **Use `delegate_task` to write 3-4 chapters in parallel** — provide full story context, character profiles, chapter outlines, and formatting rules
4. **Chapters are written to files** at `/root/novel/chapter<N>_<标题>.txt`
5. **Publish one by one** through the browser

`delegate_task` example structure:
```
delegate_task(
  context="Full story summary, character descriptions, existing chapters summary",
  goal="Write chapters X, Y, Z in Chinese with proper paragraph breaks",
  toolsets=["file", "terminal"]
)
```

## Direct Publish URL (Alternative to SPA Click-through)

If the SPA buttons fail to navigate, use direct URL:
```
browser_navigate("https://fanqienovel.com/main/writer/<bookId>/publish?enter_from=chapter_manage")
```
This opens the editor directly. The chapter ID is auto-generated.

The "存草稿" and "下一步" buttons are **initially disabled** — they activate once title and content are filled.

## 4-Step Tutorial Wizard (Publish Entry)

When entering the publish editor via certain URL paths, a **4-step tutorial wizard** appears after clicking "下一步". Each step has a "下一步" or "我知道了" button (same ref=e3 pattern):

- **Step 1/4 — 分卷设置:** Volume selection. Click "下一步".
- **Step 2/4 — AI写作功能介绍:** AI writing features intro. Click "下一步".
- **Step 3/4 — 灵感功能:** Inspiration/lore features. Click "下一步".
- **Step 4/4 — 大纲/人物卡片:** Outline & character cards intro. Click "我知道了".

After the wizard closes, the standard publishing dialogs appear (typo check → risk detection → publish settings).

## Known Pitfalls

0. **Chapter list truncated / display error** — The chapter management table may only show ~5 chapters even though more exist. This is a snapshot/rendering issue. Fix: use `browser_navigate` to reload the chapter management URL directly (the one from the address bar), which forces a full page refresh and shows all chapters.

1. **SPA navigation fails on direct URL** — `browser_navigate` to `chapter?bookId=` returns 404. Always navigate via clicking through from the workbench.
2. **ProseMirror formatting is flat** — `browser_type` dumps all text as one paragraph (no breaks). After typing, use JS innerHTML with `<p>` tags to split into proper paragraphs (see Option 1 above). Don't try to set content via innerHTML alone — ProseMirror won't register it as valid content. Use browser_type first, then fix formatting.
3. **Session expires** — the login session may expire between sessions. If workbench shows public page instead of writer dashboard, need to re-login.
4. **Persistent browser (port 9222) required** — ephemeral headless instances lose cookies on crash/restart. Configure Hermes to use the persistent visible browser at port 9222 for stable sessions across navigations.
5. **Chapter preview shows truncated content** — the read/preview page may only show first ~100 chars or just the first sentence. Scrolling may not reveal more. Use the edit button to open the full editor view instead.
6. **"下一步" click loops on first try** — clicking "下一步" from the editor may show the typo dialog; if you cancel and click "下一步" again, it shows the same dialog. Use "忽略全部" on the typo panel (bottom of page) to clear all typo warnings, then try "下一步" again.
7. **AI checkbox not on main editor page** — don't waste time searching for the AI checkbox in the editor. It only appears as radio buttons ("是"/"否") in the **final "发布设置" dialog** after passing through the typo and risk-detection dialogs.
8. **AI radio button click may fail in "发布设置" dialog** — The "是" (AI use) radio button sometimes refuses to register clicks, even when clicking both the `<input type="radio">` and its wrapping LabelText element. The button's `checked` property may remain `false` despite programmatic clicks. **Workaround:** Close the dialog, click "存草稿" to save as draft, then navigate to the "草稿箱" tab, click the draft chapter title, re-enter the publish flow from there — the radio buttons often work on the second attempt.
9. **存草稿 as fallback when publish is stuck** — If the "发布设置" dialog appears but buttons won't respond, close it (× button at ref=e3), then click "存草稿". The chapter is saved as a draft. Access it later from 草稿箱 tab → click title → re-publish.
10. **Chapter number and title get cleared on page re-render** — After filling in body content via JS, clicking "下一步" may trigger a page re-render (e.g., switching from "已保存" to "保存中" to "已保存到云端"). This re-render can **clear the chapter number and title textboxes** while preserving body content. Always verify both fields are populated before clicking "下一步". Re-fill with `browser_type` if empty.
9. **Editing published chapters to fix formatting** — To fix paragraph breaks on an already-published chapter: click the edit icon (not the title link) in chapter management → editor opens → use JS innerHTML fix → click "下一步" → go through the full dialog chain (typos → risk detection → publish settings with AI radio → confirm). The chapter re-enters review after update.
