/**
 * BS2 vs BS5 parity: exhaustive DOM + computed-style extractor.
 *
 * Run this whole file as a single expression via the Browser MCP tool's
 * `javascript_tool` action (read-only inspection only — never used to
 * change the page). Its return value is JSON-serializable; paste the tool
 * result straight into a file for dev-tools/bs-parity/diff.py to consume.
 *
 * Usage from the harness:
 *   1. Log in + navigate + resize the tab to the target viewport width.
 *   2. Run this file's contents via javascript_tool.
 *   3. Write the returned value (already JSON) to old-<page>-<width>.json
 *      or new-<page>-<width>.json.
 *   4. Repeat for the other app/tab.
 *   5. node/python: dev-tools/bs-parity/diff.py old.json new.json
 *
 * Optional: set window.__BS_PARITY_ROOT__ = 'selector' before running to
 * scope extraction to a container instead of the full <body> (e.g. to keep
 * payloads small on pages with huge tables). Defaults to 'body'.
 */
(function () {
  var STYLE_PROPS = [
    'display', 'position', 'boxSizing', 'float', 'clear',
    'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
    'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
    'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
    'borderTopStyle', 'borderRightStyle', 'borderBottomStyle', 'borderLeftStyle',
    'borderTopColor', 'borderRightColor', 'borderBottomColor', 'borderLeftColor',
    'borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomRightRadius', 'borderBottomLeftRadius',
    'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing',
    'textAlign', 'textDecorationLine', 'textDecorationColor', 'textDecorationStyle',
    'textTransform', 'textShadow', 'whiteSpace', 'verticalAlign',
    'color', 'backgroundColor', 'backgroundImage', 'opacity',
    'boxShadow', 'outlineWidth', 'outlineStyle', 'outlineColor', 'cursor',
    'overflowX', 'overflowY', 'zIndex', 'listStyleType',
    'flexDirection', 'flexWrap', 'justifyContent', 'alignItems', 'alignSelf',
    'flexGrow', 'flexShrink', 'flexBasis', 'gap', 'order'
  ];

  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, TEMPLATE: 1, NOSCRIPT: 1, LINK: 1, META: 1 };

  function ownText(el) {
    var t = '';
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) t += n.nodeValue;
    }
    return t.replace(/\s+/g, ' ').trim();
  }

  function attrs(el) {
    var a = {};
    if (el.tagName === 'A' && el.getAttribute('href')) a.href = el.getAttribute('href');
    var title = el.getAttribute('title');
    if (title) a.title = title;
    var type = el.getAttribute('type');
    if (type) a.type = type;
    var name = el.getAttribute('name');
    if (name) a.name = name;
    var value = el.getAttribute('value');
    if (value !== null && value !== undefined) a.value = value;
    for (var i = 0; i < el.attributes.length; i++) {
      var at = el.attributes[i];
      if (at.name.indexOf('data-') === 0) a[at.name] = at.value;
    }
    return a;
  }

  function walk(el, path, out) {
    if (!el || el.nodeType !== 1 || SKIP_TAGS[el.tagName]) return;
    var cs = window.getComputedStyle(el);
    if (cs.display === 'none') return;

    var rect = el.getBoundingClientRect();
    var style = {};
    for (var i = 0; i < STYLE_PROPS.length; i++) {
      style[STYLE_PROPS[i]] = cs.getPropertyValue(
        STYLE_PROPS[i].replace(/[A-Z]/g, function (m) { return '-' + m.toLowerCase(); })
      );
    }

    out.push({
      path: path,
      tag: el.tagName,
      id: el.id || undefined,
      text: ownText(el) || undefined,
      rect: [
        Math.round(rect.x * 100) / 100,
        Math.round(rect.y * 100) / 100,
        Math.round(rect.width * 100) / 100,
        Math.round(rect.height * 100) / 100
      ],
      attrs: attrs(el),
      style: style
    });

    if (el.tagName === 'SVG') return; // keep the node, skip its internals

    var childIdx = 0;
    for (var c = 0; c < el.children.length; c++) {
      walk(el.children[c], path + '.' + childIdx, out);
      childIdx++;
    }
  }

  var rootSel = window.__BS_PARITY_ROOT__ || 'body';
  var root = document.querySelector(rootSel);
  var out = [];
  if (root) walk(root, '0', out);

  return {
    url: location.href,
    viewport: [window.innerWidth, window.innerHeight],
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    count: out.length,
    elements: out
  };
})();
