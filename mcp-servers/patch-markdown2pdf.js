const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'node_modules', 'markdown2pdf-mcp', 'build', 'index.js');
const cssPath = path.join(__dirname, 'node_modules', 'markdown2pdf-mcp', 'build', 'css', 'pdf.css');

if (!fs.existsSync(filePath)) {
  console.error('markdown2pdf-mcp build/index.js not found, skipping patch.');
  process.exit(0);
}

let content = fs.readFileSync(filePath, 'utf8');

// Patch 1: Change default paperOrientation from portrait to landscape (schema description)
content = content.replace(
  /description:\s*'Paper orientation for the PDF \(default:\s*portrait\)'/,
  "description: 'Paper orientation for the PDF (default: landscape)'"
);

// Patch 2: Change default paperOrientation from portrait to landscape (schema default)
content = content.replace(
  /paperOrientation:\s*\{[^}]*default:\s*'portrait'/,
  (match) => match.replace("default: 'portrait'", "default: 'landscape'")
);

// Patch 3: Change runtime default from portrait to landscape (global replace)
content = content.replace(
  /paperOrientation = 'portrait'/g,
  "paperOrientation = 'landscape'"
);

// Patch 4: Change default paperBorder from 2cm to 1.5cm for balanced margins
if (!content.includes("paperBorder = '1.5cm'")) {
  // Update schema description
  content = content.replace(
    /description:\s*'Border margin for the PDF \(default:\s*(?:2cm|1cm|0\.5cm)\)'/,
    "description: 'Border margin for the PDF (default: 1.5cm)'"
  );
  // Update runtime defaults
  content = content.replace(/paperBorder = '2cm'/g, "paperBorder = '1.5cm'");
  content = content.replace(/paperBorder = '1cm'/g, "paperBorder = '1.5cm'");
  content = content.replace(/paperBorder = '0.5cm'/g, "paperBorder = '1.5cm'");
}

// Patch 5: Add download URL to output (if not already patched)
if (!content.includes('Download URL:')) {
  content = content.replace(
    /progressUpdates\.push\(\s*`File exists:\s*\$\{fs\.existsSync\(absolutePath\)\}`\s*\);/,
    (match) =>
      `${match}
                const pdfFilename = path.basename(absolutePath);
                progressUpdates.push(\`Download URL: /api/files/mcp/pdf/\${encodeURIComponent(pdfFilename)}\`);
                progressUpdates.push(\`IMPORTANT: When presenting the download link to the user, use this exact markdown format: [\${pdfFilename}](/api/files/mcp/pdf/\${encodeURIComponent(pdfFilename)})\`);`
  );
}

// Patch 6: Force showPageNumbers to always be false (ignore model input)
// Only apply if not already patched (idempotent check)
if (!content.includes('showPageNumbers: _showPageNumbers')) {
  content = content.replace(
    /showPageNumbers\s*=\s*false\s*\}\s*=\s*args;/,
    'showPageNumbers: _showPageNumbers = false } = args; const showPageNumbers = false;'
  );
}

// Patch 8: Force paperOrientation to always be landscape (ignore model input)
// Only apply if not already patched
if (!content.includes('paperOrientation: _ignoredPaperOrientation')) {
  // 1. Rename the destructured property to ignore input
  // targeting the specific context in CallToolRequest destructuring
  content = content.replace(
    /paperOrientation\s*=\s*'[^']*'\s*,\s*paperBorder/,
    "paperOrientation: _ignoredPaperOrientation = 'landscape', paperBorder"
  );

  // 2. Define the constant variable (appending to the end of the const block created largely by Patch 6)
  // We hook onto 'const showPageNumbers = false;' which we presume exists from Patch 6
  // Check if Patch 6 has run by looking for showPageNumbers: _showPageNumbers
  if (content.includes('showPageNumbers: _showPageNumbers')) {
    content = content.replace(
      "const showPageNumbers = false;",
      "const showPageNumbers = false; const paperOrientation = 'landscape';"
    );
  } else {
    // Fallback: inject the constant right after args destructuring
    if (!content.includes("const paperOrientation = 'landscape';")) {
      content = content.replace(
        /paperOrientation[\s\S]*?\}\s*=\s*args;/,
        (match) => `${match} const paperOrientation = 'landscape';`
      );
    }
  }
}

// Patch 10: Fix .page width for landscape mode
// The original hardcodes .page width to 8.5in (portrait) even in landscape,
// causing content to be narrower than the page with extra whitespace on the right.
if (!content.includes('pageWidth')) {
  content = content.replace(
    "width: ${paperFormat === 'letter' ? '8.5in' : '210mm'}",
    "width: ${(() => { const pageWidth = paperFormat === 'letter' ? (paperOrientation === 'landscape' ? '11in' : '8.5in') : (paperOrientation === 'landscape' ? '297mm' : '210mm'); return pageWidth; })()}"
  );
}

// Patch 9: Update tool description to mention page breaks
if (!content.includes('page-break')) {
  content = content.replace(
    "Mermaid syntax errors will be displayed directly in the PDF output.'",
    "Mermaid syntax errors will be displayed directly in the PDF output. To insert a page break, use <div class=\"page-break\"></div> in the markdown. Tables, headings, and blockquotes will automatically avoid being split across pages.'"
  );
}

// Patch 11: Inject cover page HTML before the content div
// The cover page shows: date (top-left), "INVESTMENT MEMO" (center), "InfinityCapital" (bottom-left), gold bars (bottom-right)
if (!content.includes('cover-page')) {
  content = content.replace(
    '<div id="mermaid-error" style="display: none; color: red;"></div>',
    `<div id="mermaid-error" style="display: none; color: red;"></div>
    <div class="cover-page">
      <div class="cover-date">\${new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' }).toUpperCase()}</div>
      <div class="cover-title">INVESTMENT MEMO</div>
      <div class="cover-bottom">
        <div class="cover-branding"><svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -15 830 150" height="50"><g transform="matrix(0.635,0,0,0.635,-213.63,-268.16)"><g opacity="1" transform="matrix(1,0,0,1,443.831,531.449)"><path fill="#282828" d="M12.651,-60.065C-3.306,-60.065-14.019,-53.454-21.997,-40.917L-22.681,-40.917L-22.681,-56.874L-53,-56.874L-53,60.065L-21.997,60.065L-21.997,-6.269C-21.997,-22.226-11.967,-33.167,1.71,-33.167C14.703,-33.167,21.998,-24.277,21.998,-11.74L21.998,60.065L53,60.065L53,-16.299C53,-41.829,36.814,-60.065,12.651,-60.065z"/></g><g opacity="1" transform="matrix(1,0,0,1,534.439,509.852)"><path fill="#282828" d="M-18.008,-45.762L-18.008,-35.276L-33.965,-35.276L-33.965,-13.849L-18.008,-13.849L-18.008,81.663L12.993,81.663L12.993,-13.849L33.965,-13.849L33.965,-35.276L12.993,-35.276L12.993,-43.938C12.993,-56.02,19.376,-57.843,33.965,-57.159L33.965,-81.094C4.103,-84.285,-18.008,-74.256,-18.008,-45.762z"/></g><g opacity="1" transform="matrix(1,0,0,1,597.81,533.045)"><path fill="#282828" d="M-15.501,58.469L15.501,58.469L15.501,-58.469L-15.501,-58.469z"/></g><g opacity="1" transform="matrix(1,0,0,1,597.81,442.435)"><path fill="#282828" d="M-15.501,13.905L15.501,13.905L15.501,-13.905L-15.501,-13.905z"/></g><g opacity="1" transform="matrix(1,0,0,1,679.524,531.449)"><path fill="#282828" d="M12.651,-60.065C-3.306,-60.065-14.019,-53.454-21.997,-40.917L-22.681,-40.917L-22.681,-56.874L-53,-56.874L-53,60.065L-21.997,60.065L-21.997,-6.269C-21.997,-22.226-11.967,-33.167,1.71,-33.167C14.703,-33.167,21.998,-24.277,21.998,-11.74L21.998,60.065L53,60.065L53,-16.299C53,-41.829,36.814,-60.065,12.651,-60.065z"/></g><g opacity="1" transform="matrix(1,0,0,1,760.328,533.045)"><path fill="#282828" d="M-15.501,58.469L15.501,58.469L15.501,-58.469L-15.501,-58.469z"/></g><g opacity="1" transform="matrix(1,0,0,1,760.328,442.435)"><path fill="#282828" d="M-15.501,13.905L15.501,13.905L15.501,-13.905L-15.501,-13.905z"/></g><g opacity="1" transform="matrix(1,0,0,1,815.832,514.923)"><path fill="#282828" d="M12.879,42.171L12.879,-19.832L32.939,-19.832L32.939,-40.347L12.879,-40.347L12.879,-76.819L-17.438,-76.819L-17.438,-40.347L-33.623,-40.347L-33.623,-19.832L-17.438,-19.832L-17.438,48.782C-17.438,70.893-0.799,76.819,14.247,76.819C26.557,76.819,33.623,76.364,33.623,76.364L33.623,53.569L28.38,53.797C24.505,53.797,12.879,50.833,12.879,42.171z"/></g><g opacity="1" transform="matrix(1,0,0,1,906.779,552.193)"><path fill="#282828" d="M24.96,-77.617L8.548,-24.961C4.901,-14.247,1.709,0.571,1.709,0.571L1.253,0.571C1.253,0.571-2.622,-14.247-6.269,-24.961L-23.594,-77.617L-56.19,-77.617L-24.733,5.584C-18.122,23.365-15.843,30.887-15.843,37.27C-15.843,46.844-20.858,53.227-33.167,53.227L-44.109,53.227L-44.109,77.617L-25.873,77.617C-2.166,77.617,6.496,68.271,15.386,42.285L56.19,-77.617z"/></g><g transform="matrix(1,0,0,1,1.25,0)"><g opacity="1" transform="matrix(1,0,0,1,1034.995,510.136)"><path fill="#282828" d="M5.472,57.672C-21.882,57.672-39.207,33.737-39.207,0.456C-39.207,-31.913-24.847,-56.988,5.243,-56.988C24.391,-56.988,36.7,-46.275,39.664,-29.862L72.489,-29.862C69.069,-60.863,45.362,-84.798,5.243,-84.798C-42.855,-84.798-72.944,-47.869-72.944,0.456C-72.944,49.466-40.346,84.798,5.472,84.798C28.038,84.798,43.767,77.959,54.937,67.473C65.878,57.215,72.033,43.311,72.944,28.95L40.575,28.95C38.524,46.046,24.847,57.672,5.472,57.672z"/></g><g opacity="1" transform="matrix(1,0,0,1,1164.58,532.931)"><path fill="#282828" d="M50.491,41.259L50.491,-18.236C50.491,-45.59,36.358,-61.319,1.254,-61.319C-32.939,-61.319-48.212,-43.311-49.124,-22.795L-21.542,-22.795C-20.63,-33.965-13.563,-39.208,1.026,-39.208C14.019,-39.208,20.629,-33.737,20.629,-25.303C20.629,-16.413,11.74,-14.817-7.636,-12.082C-33.622,-8.435-54.594,-0.228-54.594,25.531C-54.594,48.782-37.727,61.319-13.791,61.319C6.268,61.319,14.703,54.481,20.629,45.59L21.085,45.59C21.77,50.832,22.909,56.304,24.733,58.583L54.594,58.583L54.594,57.444C51.859,55.392,50.491,50.149,50.491,41.259zM21.313,17.325C21.313,28.721,11.512,39.664-6.269,39.664C-17.21,39.664-24.505,35.788-24.505,24.846C-24.505,13.905-16.527,10.258-0.341,6.611C7.409,4.787,15.842,2.963,21.313,-0.228z"/></g><g opacity="1" transform="matrix(1,0,0,1,1285.729,550.597)"><path fill="#282828" d="M7.066,-79.213C-8.89,-79.213-19.832,-71.691-27.354,-61.433L-28.038,-61.433L-28.038,-76.022L-57.899,-76.022L-57.899,79.213L-26.898,79.213L-26.898,27.696L-26.442,27.696C-19.832,37.726-9.118,44.336,7.294,44.336C37.384,44.336,57.899,20.402,57.899,-17.438C57.899,-53.91,38.067,-79.213,7.066,-79.213zM0.684,18.578C-17.78,18.578-27.583,4.673-27.583,-16.527C-27.583,-37.498-19.832,-54.138-0.456,-54.138C18.692,-54.138,26.442,-38.638,26.442,-16.527C26.442,5.584,16.413,18.578,0.684,18.578z"/></g><g opacity="1" transform="matrix(1,0,0,1,1366.647,442.435)"><path fill="#282828" d="M-15.501,13.905L15.501,13.905L15.501,-13.905L-15.501,-13.905z"/></g><g opacity="1" transform="matrix(1,0,0,1,1366.647,533.045)"><path fill="#282828" d="M-15.501,58.469L15.501,58.469L15.501,-58.469L-15.501,-58.469z"/></g><g opacity="1" transform="matrix(1,0,0,1,1422.152,514.923)"><path fill="#282828" d="M12.879,42.171L12.879,-19.832L32.938,-19.832L32.938,-40.347L12.879,-40.347L12.879,-76.819L-17.438,-76.819L-17.438,-40.347L-33.623,-40.347L-33.623,-19.832L-17.438,-19.832L-17.438,48.782C-17.438,70.893-0.799,76.819,14.246,76.819C26.557,76.819,33.623,76.364,33.623,76.364L33.623,53.569L28.379,53.797C24.504,53.797,12.879,50.833,12.879,42.171z"/></g><g opacity="1" transform="matrix(1,0,0,1,1514.236,532.931)"><path fill="#282828" d="M50.491,41.259L50.491,-18.236C50.491,-45.59,36.358,-61.319,1.254,-61.319C-32.939,-61.319-48.211,-43.311-49.123,-22.795L-21.541,-22.795C-20.629,-33.965-13.563,-39.208,1.025,-39.208C14.019,-39.208,20.629,-33.737,20.629,-25.303C20.629,-16.413,11.74,-14.817-7.637,-12.082C-33.623,-8.435-54.594,-0.228-54.594,25.531C-54.594,48.782-37.727,61.319-13.791,61.319C6.269,61.319,14.703,54.481,20.629,45.59L21.086,45.59C21.77,50.832,22.909,56.304,24.732,58.583L54.594,58.583L54.594,57.444C51.86,55.392,50.491,50.149,50.491,41.259zM21.313,17.325C21.313,28.721,11.511,39.664-6.269,39.664C-17.211,39.664-24.505,35.788-24.505,24.846C-24.505,13.905-16.527,10.258-0.342,6.611C7.408,4.787,15.842,2.963,21.313,-0.228z"/></g></g></g><g transform="matrix(0.637,0,0,0.637,-214.83,-269.49)"><g opacity="1" transform="matrix(1,0,0,1,358.353,510.022)"><path fill="#282828" d="M-16.527,81.492L16.527,81.492L16.527,-81.492L-16.527,-81.492z"/></g></g><g transform="matrix(0.637,0,0,0.637,-218.80,-269.46)"><g opacity="1" transform="matrix(1,0,0,1,1596.749,510.022)"><path fill="#282828" d="M-16.527,-81.492L-16.527,81.492L16.527,81.492L16.527,-81.492z"/></g></g></svg></div>
      </div>
    </div>`
  );
}

fs.writeFileSync(filePath, content, 'utf8');
console.log('markdown2pdf-mcp index.js patched successfully.');

// Patch 7: Replace CSS with corporate styling (gold/black/charcoal theme)
const corporateCSS = `/* Corporate PDF Theme - Gold & Black */
/* Matching Infinity Capital investment memo styling */

.watermark {
  position: fixed;
  top: 50%;
  left: 50%;
  color: rgba(168, 153, 104, 0.2);
  -webkit-transform-origin: center;
  transform-origin: center;
  -webkit-transform: translate(-50%, -50%) rotate(-45deg);
  transform: translate(-50%, -50%) rotate(-45deg);
  white-space: nowrap;
  pointer-events: none;
  user-select: none;
  z-index: 1000;
}

body {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: #333333;
  background-color: #fff;
  margin: 0;
  padding: 0;
  width: 100%;
}

/* Headings - large, clean, black */
h1 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 300;
  font-size: 32px;
  line-height: 1.2;
  color: #000000;
  margin-top: 24px;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 3px solid #A89968;
}

h2 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 400;
  font-size: 22px;
  line-height: 1.2;
  color: #ffffff;
  background-color: #545454;
  margin-top: 20px;
  margin-bottom: 12px;
  padding: 8px 14px;
}

h3 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 500;
  font-size: 17px;
  line-height: 1.3;
  color: #A89968;
  margin-top: 16px;
  margin-bottom: 8px;
  border-bottom: 1px solid #A89968;
  padding-bottom: 4px;
}

h4 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 600;
  font-size: 14px;
  line-height: 1.3;
  color: #333333;
  margin-top: 14px;
  margin-bottom: 6px;
}

h5, h6 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: 600;
  font-size: 12px;
  line-height: 1.3;
  color: #545454;
  margin-top: 10px;
  margin-bottom: 4px;
}

/* Paragraphs */
p {
  margin-top: 0;
  margin-bottom: 10px;
}

/* Strong / Bold - used for key callouts */
strong {
  font-weight: 700;
  color: #000000;
}

/* Lists */
ul, ol {
  padding-left: 24px;
  margin-top: 6px;
  margin-bottom: 10px;
}

li {
  margin-bottom: 4px;
  line-height: 1.5;
}

/* Nested list items */
li > ul, li > ol {
  margin-top: 4px;
  margin-bottom: 4px;
}

/* Tables - professional corporate styling */
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
  margin-bottom: 16px;
  font-size: 12px;
  line-height: 1.4;
}

thead th {
  background-color: #333333;
  color: #ffffff;
  font-weight: 600;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid #333333;
  font-size: 12px;
}

tbody td {
  padding: 6px 10px;
  border: 1px solid #dddddd;
  vertical-align: top;
}

/* Alternating row colors */
tbody tr:nth-child(even) {
  background-color: #f7f6f2;
}

tbody tr:nth-child(odd) {
  background-color: #ffffff;
}

/* Hover-like emphasis for first column (category labels) */
tbody td:first-child {
  font-weight: 600;
  color: #333333;
}

/* Code blocks */
code {
  font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
  padding: 2px 5px;
  font-size: 90%;
  color: #333333;
  background-color: #f7f6f2;
  border-radius: 3px;
  border: 1px solid #e0ddd5;
}

pre {
  display: block;
  padding: 12px;
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #333333;
  word-break: break-all;
  word-wrap: break-word;
  background-color: #f7f6f2;
  border: 1px solid #e0ddd5;
  border-radius: 4px;
  border-left: 4px solid #A89968;
}

pre code {
  padding: 0;
  font-size: inherit;
  color: inherit;
  white-space: pre-wrap;
  background-color: transparent;
  border-radius: 0;
  border: none;
}

/* Blockquotes - gold accent bar */
blockquote {
  margin: 12px 0;
  padding: 10px 16px;
  border-left: 4px solid #A89968;
  background-color: #faf9f5;
  color: #545454;
  font-style: normal;
}

blockquote p {
  margin-bottom: 0;
}

/* Horizontal rules */
hr {
  border: none;
  border-top: 2px solid #A89968;
  margin: 20px 0;
}

/* Links */
a {
  color: #A89968;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* Red callout text (for important warnings/highlights) */
em {
  font-style: italic;
  color: #C00000;
}

/* Page break support - use <div class="page-break"></div> in markdown */
.page-break {
  page-break-after: always;
  break-after: page;
}

/* Prevent tables from being split across pages */
table {
  page-break-inside: avoid;
  break-inside: avoid;
}

/* Prevent headings from being orphaned at bottom of page */
h1, h2, h3, h4, h5, h6 {
  page-break-after: avoid;
  break-after: avoid;
}

/* Keep list items together */
li {
  page-break-inside: avoid;
  break-inside: avoid;
}

/* Keep blockquotes together */
blockquote {
  page-break-inside: avoid;
  break-inside: avoid;
}

/* Cover Page Styles */
.cover-page {
  --cover-edge: 40px;
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: 20px var(--cover-edge);
  page-break-after: always;
  break-after: page;
  page-break-inside: avoid;
  break-inside: avoid;
}

/* Ensure the page box matches the actual PDF page size in landscape */
.page {
  width: 100%;
  height: 100%;
}

.cover-date {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 13px;
  font-weight: 400;
  color: #333333;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.cover-title {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 42px;
  font-weight: 300;
  color: #A89968;
  letter-spacing: 0.5px;
  margin: 0;
  line-height: 1.2;
  position: absolute;
  top: 50%;
  left: var(--cover-edge);
  transform: translateY(-50%);
}

.cover-bottom {
  position: absolute;
  bottom: 0;
  left: var(--cover-edge);
  right: var(--cover-edge);
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.cover-branding {
  display: flex;
  align-items: flex-end;
  line-height: 0;
  overflow: visible;
}

.cover-branding svg {
  height: 48px;
  width: auto;
  overflow: visible;
  display: block;
}
`;

fs.writeFileSync(cssPath, corporateCSS, 'utf8');
console.log('markdown2pdf-mcp CSS patched with corporate theme.');
