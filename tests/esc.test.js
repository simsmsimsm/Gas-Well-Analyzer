/**
 * Tests for the esc() XSS sanitiser defined in static/app.js.
 *
 * app.js uses browser globals (document, Plotly, fetch) at the top level,
 * so we cannot import the whole file. Instead we read it, extract the
 * esc() function body, and evaluate it in isolation.
 */
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(
  path.resolve(__dirname, "../static/app.js"),
  "utf8"
);

// Extract the esc function source and evaluate it.
const match = src.match(/function esc\s*\(s\)\s*\{[\s\S]*?\n\}/);
if (!match) throw new Error("Could not locate esc() in app.js");
// eslint-disable-next-line no-new-func
const esc = new Function(`${match[0]}; return esc;`)();

// ---------------------------------------------------------------------------
// Basic passthrough
// ---------------------------------------------------------------------------

test("plain text is returned unchanged", () => {
  expect(esc("hello world")).toBe("hello world");
});

test("numbers are coerced to strings", () => {
  expect(esc(42)).toBe("42");
});

test("empty string returns empty string", () => {
  expect(esc("")).toBe("");
});

// ---------------------------------------------------------------------------
// Null / undefined coercion
// ---------------------------------------------------------------------------

test("null returns empty string", () => {
  expect(esc(null)).toBe("");
});

test("undefined returns empty string", () => {
  expect(esc(undefined)).toBe("");
});

// ---------------------------------------------------------------------------
// HTML character escaping
// ---------------------------------------------------------------------------

test("ampersand is escaped", () => {
  expect(esc("a & b")).toBe("a &amp; b");
});

test("less-than is escaped", () => {
  expect(esc("<")).toBe("&lt;");
});

test("greater-than is escaped", () => {
  expect(esc(">")).toBe("&gt;");
});

test("double-quote is escaped", () => {
  expect(esc('"')).toBe("&quot;");
});

// ---------------------------------------------------------------------------
// XSS payloads
// ---------------------------------------------------------------------------

test("script tag is neutralised", () => {
  const result = esc('<script>alert("xss")</script>');
  expect(result).not.toContain("<script>");
  expect(result).not.toContain("</script>");
  expect(result).toContain("&lt;script&gt;");
});

test("img onerror payload is neutralised", () => {
  const result = esc('<img src=x onerror="evil()">');
  expect(result).not.toContain("<img");
  expect(result).toContain("&lt;img");
});

test("attribute injection via double-quote is neutralised", () => {
  const result = esc('" onmouseover="evil()');
  expect(result).not.toContain('"');
  expect(result).toContain("&quot;");
});

// ---------------------------------------------------------------------------
// Multiple replacements in one string
// ---------------------------------------------------------------------------

test("all four special characters escaped in one string", () => {
  expect(esc('<a href="x">foo & bar</a>')).toBe(
    "&lt;a href=&quot;x&quot;&gt;foo &amp; bar&lt;/a&gt;"
  );
});

test("ampersand is not double-escaped", () => {
  // If "&" were replaced twice, "&amp;" would become "&amp;amp;"
  expect(esc("&amp;")).toBe("&amp;amp;");
});

// ---------------------------------------------------------------------------
// Single-quote: NOT escaped (documents current behaviour)
// ---------------------------------------------------------------------------

test("single-quote is NOT escaped (known limitation)", () => {
  // The function does not escape apostrophes. This test documents that.
  // If the function is updated to escape single-quotes, update this test.
  expect(esc("it's")).toBe("it's");
});
