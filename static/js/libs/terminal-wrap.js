/* Word-wrap text for jQuery Terminal (story-mode transmissions).
   The bundled terminal hard-splits lines at exactly its column count, which
   breaks words mid-way ("infor / mation"). Wrap at word boundaries first,
   one column short of the terminal width: the browser can fit one column
   fewer than the terminal calculates, which otherwise causes a second wrap.
   Formatting such as [[b;;]text] is preserved; a line whose formatted span
   contains spaces is passed through unchanged rather than split inside it. */
function wrapForTerminal(text, cols) {
    var width = Math.max(10, cols - 1);
    function visibleLength(s) {
        return s.replace(/\[\[[^\]]*\]/g, "").replace(/\]/g, "").length;
    }
    return String(text).split("\n").map(function (line) {
        if (/\[\[[^\]]*\][^\]]* /.test(line)) {
            return line;
        }
        var lines = [];
        var current = "";
        line.split(" ").forEach(function (word) {
            var candidate = current ? current + " " + word : word;
            if (current && visibleLength(candidate) > width) {
                lines.push(current);
                current = word;
            } else {
                current = candidate;
            }
        });
        lines.push(current);
        return lines.join("\n");
    }).join("\n");
}
