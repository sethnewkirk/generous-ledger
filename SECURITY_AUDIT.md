# Security & Functionality Audit Report
## Generous Ledger Obsidian Plugin

**Audit Date:** 2026-01-06
**Auditor:** Claude Code
**Status:** ⚠️ Issues Found - Fixes Recommended Before Production Use

---

## 🔴 CRITICAL ISSUES

### 1. Race Condition in Request Processing (main.ts:140)
**Severity:** High
**File:** `src/main.ts` lines 138-141

**Issue:**
```typescript
if (!content.trim()) {
    new Notice('Please provide content for Claude to respond to');
    return;  // ❌ Returns without resetting processingRequest flag
}
```

**Impact:** If validation fails after `processingRequest = true`, the flag never resets. Plugin becomes permanently locked and cannot process any future requests.

**Fix Required:** Move flag to finally block or reset before all early returns.

---

### 2. Paragraph Boundary Bug (paragraphExtractor.ts:30)
**Severity:** High
**File:** `src/editor/paragraphExtractor.ts` lines 29-36

**Issue:**
```typescript
while (currentLineNum < doc.lines) {
    const nextLine = doc.line(currentLineNum + 1);  // ❌ Can exceed bounds
```

**Impact:** When cursor is on the last line of document, `currentLineNum` can equal `doc.lines`, then `currentLineNum + 1` causes out-of-bounds error. This will crash the plugin.

**Fix Required:** Change condition to `currentLineNum < doc.lines` AND check before accessing +1.

---

### 3. Missing Null Check for API Response (claudeClient.ts:35)
**Severity:** Medium
**File:** `src/api/claudeClient.ts` line 35

**Issue:**
```typescript
if (message.content[0].type === 'text') {  // ❌ Assumes content[0] exists
    return message.content[0].text;
}
```

**Impact:** If Claude API returns empty `content` array, this will throw "Cannot read property '0' of undefined" error.

**Fix Required:** Check `message.content && message.content.length > 0` first.

---

## 🟡 MEDIUM ISSUES

### 4. Stale Variable Reference (main.ts:162)
**Severity:** Medium
**File:** `src/main.ts` lines 122, 162-169

**Issue:**
```typescript
const mentionPos = findClaudeMentionInView(view);  // Line 122
// ... async operation ...
// Later in catch block (line 162):
if (mentionPos !== null) {  // ❌ Using stale value after async operation
```

**Impact:** Between capturing `mentionPos` and using it in error handler, user could have edited the document. The position might be invalid or point to wrong location.

**Fix Required:** Recalculate `mentionPos` in error handler or verify position is still valid.

---

### 5. Global Keydown Listener Scope (main.ts:29)
**Severity:** Medium
**File:** `src/main.ts` lines 28-33

**Issue:**
```typescript
this.registerDomEvent(document, 'keydown', (evt: KeyboardEvent) => {
    if (evt.key === 'Enter' && !evt.shiftKey) {
        this.handleEnterKey(evt);  // ❌ Fires for ALL Enter keys in app
    }
});
```

**Impact:**
- Triggers even when focus is in settings, modals, or other plugins
- Could interfere with other Obsidian functionality
- Performance overhead from checking on every keypress

**Fix Required:** Check if active element is actually an Obsidian editor before processing.

---

### 6. Document Switch During Async Operation (main.ts:144-156)
**Severity:** Medium
**File:** `src/main.ts` lines 144-156

**Issue:** No validation that the editor is still active after async API call completes.

**Impact:** User could:
1. Trigger @Claude request
2. Switch to different note during API call
3. Response gets inserted into wrong document

**Fix Required:** Store document reference and verify it's still active before inserting response.

---

## 🟢 LOW ISSUES (Best Practices)

### 7. API Key Storage (settings.ts)
**Severity:** Low (Informational)
**File:** `src/settings.ts` line 43

**Issue:** API key is stored in plain text JSON at `.obsidian/plugins/generous-ledger/data.json`

**Impact:** Anyone with file system access can read the API key. However, this is standard for Obsidian plugins.

**Recommendation:** Document this in README. Consider warning user about storing API keys in synced vaults.

---

### 8. No Input Sanitization for Responses (responseRenderer.ts:22)
**Severity:** Low
**File:** `src/renderer/responseRenderer.ts` line 22

**Issue:**
```typescript
const callout = `\n\n> [!claude] Claude's Response\n> ${response.split('\n').join('\n> ')}`;
```

**Impact:**
- No sanitization of Claude's response
- Malicious responses could inject unwanted Markdown
- Low risk since Obsidian's Markdown renderer is safe, but response could include unwanted formatting

**Recommendation:** Document that responses are inserted as-is.

---

### 9. innerHTML Usage (visualIndicator.ts:16,20,24)
**Severity:** Low
**File:** `src/editor/visualIndicator.ts` lines 16, 20, 24

**Issue:**
```typescript
span.innerHTML = '🤖';  // Should use textContent for non-HTML content
```

**Impact:** None (emojis are hardcoded), but violates best practices.

**Recommendation:** Use `span.textContent` instead of `innerHTML` for plain text.

---

### 10. No Rate Limiting
**Severity:** Low
**File:** `src/main.ts`

**Issue:** `processingRequest` prevents concurrent requests but not rapid sequential requests.

**Impact:** User could spam API calls rapidly (costs money, potential API abuse).

**Recommendation:** Add cooldown period or request queue.

---

### 11. Error Message Exposure (claudeClient.ts:42)
**Severity:** Low
**File:** `src/api/claudeClient.ts` line 42

**Issue:**
```typescript
throw new Error(`Claude API Error: ${error.message}`);
```

**Impact:** Exposes internal API error messages to user. Generally safe with Anthropic API but could leak info.

**Recommendation:** Sanitize or categorize errors before showing to user.

---

### 12. Empty Line Handling in Responses (responseRenderer.ts:22)
**Severity:** Low
**File:** `src/renderer/responseRenderer.ts` line 22

**Issue:**
```typescript
response.split('\n').join('\n> ')
```

**Impact:**
- Empty lines in response become `> ` (blockquote with space)
- Could create weird formatting
- CRLF vs LF line endings not handled

**Recommendation:** Handle empty lines explicitly: `response.split('\n').map(line => line ? `> ${line}` : '>').join('\n')`

---

## 🔵 FUNCTIONALITY OBSERVATIONS

### 13. Limited @Claude Detection Scope (claudeDetector.ts:50)
**File:** `src/editor/claudeDetector.ts` line 50

**Behavior:** Only detects `@Claude` on the current line where cursor is located.

**Impact:** If user types `@Claude` on line 1 of a paragraph and cursor is on line 2, it won't be detected.

**Note:** This might be intentional design. If not, should search entire paragraph.

---

### 14. No Maximum Content Length Validation
**File:** `src/main.ts`

**Observation:** No check for very large paragraphs before sending to API.

**Impact:**
- Large paragraphs could exceed token limits
- Performance issues with very long responses
- Higher API costs

**Recommendation:** Warn user if paragraph exceeds reasonable length (e.g., 10k characters).

---

## 📊 SECURITY SUMMARY

| Category | Count | Severity |
|----------|-------|----------|
| Critical Issues | 3 | 🔴 High |
| Medium Issues | 4 | 🟡 Medium |
| Low/Best Practice | 7 | 🟢 Low |
| **Total Issues** | **14** | - |

---

## ✅ GOOD SECURITY PRACTICES FOUND

1. ✅ API key hidden with password input field
2. ✅ TypeScript type safety throughout
3. ✅ Error handling for API calls
4. ✅ No eval() or dangerous code execution
5. ✅ No external dependencies beyond official SDK
6. ✅ Proper use of Obsidian's plugin lifecycle
7. ✅ Concurrent request prevention

---

## 🔧 RECOMMENDED FIXES (Priority Order)

### Must Fix Before Testing:
1. **Fix race condition** in `main.ts:140` - Reset `processingRequest` in finally block
2. **Fix boundary bug** in `paragraphExtractor.ts:30` - Add bounds checking
3. **Add null check** in `claudeClient.ts:35` - Verify content array

### Should Fix Before Production:
4. Recalculate `mentionPos` in error handler or validate position
5. Scope keydown listener to editor elements only
6. Validate document is still active after async operation

### Nice to Have:
7. Add rate limiting
8. Improve line ending handling in responses
9. Use `textContent` instead of `innerHTML`
10. Document API key storage security

---

## 📝 TESTING RECOMMENDATIONS

Before deploying, test these scenarios:

1. **Empty content:** Type "@Claude" with no text and press Enter
2. **Last line:** Place @Claude on last line of document
3. **Document switch:** Trigger request, immediately switch documents
4. **Rapid requests:** Press Enter multiple times quickly
5. **Very long paragraph:** Test with 5000+ word paragraph
6. **Special characters:** Test response with `<script>`, `[[links]]`, etc.
7. **Empty API response:** Mock empty content array from API
8. **Network timeout:** Simulate slow/failed network

---

**Overall Assessment:** The code is well-structured and follows good patterns, but has several bugs that will cause crashes in edge cases. The critical issues must be fixed before any user testing.
