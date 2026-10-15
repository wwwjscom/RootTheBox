// Copy the browser libraries pinned in package.json into the app's static tree.
//
//   npm ci && npm run vendor
//
// The output is committed, so running the app never needs Node. CI reruns
// this script and fails if the committed files differ from the lockfile's
// versions. Never edit the copied files by hand: change the version in
// package.json, run the commands above, and commit the result.
import { cpSync, existsSync, mkdirSync, rmSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const VENDOR_DIR = 'static/vendor';

// Each library: npm package, then [source in the package, destination in the
// repo, optional filename filter]. Sources may be files or directories (the
// filter picks which files of a directory to copy). Every destination is under
// static/vendor/, the one directory CI checks for drift. `dir` names the
// folder for the licence when the package name is scoped.
const LIBRARIES = [
    { pkg: 'jquery', files: [['dist/jquery.min.js', 'static/vendor/jquery/jquery.min.js']] },
    {
        pkg: 'jquery-ui',
        files: [
            ['dist/jquery-ui.min.js', 'static/vendor/jquery-ui/jquery-ui.min.js'],
            ['dist/themes/base/jquery-ui.min.css', 'static/vendor/jquery-ui/jquery-ui.min.css'],
            ['dist/themes/base/images', 'static/vendor/jquery-ui/images'],
        ],
    },
    {
        pkg: 'bootstrap',
        files: [
            ['dist/js/bootstrap.bundle.min.js', 'static/vendor/bootstrap/bootstrap.bundle.min.js'],
            ['dist/css/bootstrap.min.css', 'static/vendor/bootstrap/bootstrap.min.css'],
        ],
    },
    {
        pkg: 'font-awesome',
        files: [
            ['css/font-awesome.min.css', 'static/vendor/font-awesome/css/font-awesome.min.css'],
            ['fonts', 'static/vendor/font-awesome/fonts'],
        ],
    },
    {
        pkg: 'jquery.terminal',
        files: [
            ['js/jquery.terminal.min.js', 'static/vendor/jquery.terminal/jquery.terminal.min.js'],
            ['css/jquery.terminal.min.css', 'static/vendor/jquery.terminal/jquery.terminal.min.css'],
        ],
    },
    {
        pkg: 'jstree',
        files: [
            ['dist/jstree.min.js', 'static/vendor/jstree/jstree.min.js'],
            ['dist/themes/default-dark', 'static/vendor/jstree/themes/default-dark'],
        ],
    },
    { pkg: 'commonmark', files: [['dist/commonmark.min.js', 'static/vendor/commonmark/commonmark.min.js']] },
    { pkg: 'clipboard', files: [['dist/clipboard.min.js', 'static/vendor/clipboard/clipboard.min.js']] },
    // Self-hosted fonts (no requests to Google Fonts). index.css declares
    // the upright variable font, one file per character set; browsers only
    // download the sets a page uses.
    {
        pkg: '@fontsource-variable/inter',
        dir: 'inter',
        files: [
            ['index.css', 'static/vendor/inter/index.css'],
            ['files', 'static/vendor/inter/files', /-wght-normal\.woff2$/],
        ],
    },
    {
        pkg: '@fontsource-variable/jetbrains-mono',
        dir: 'jetbrains-mono',
        files: [
            ['index.css', 'static/vendor/jetbrains-mono/index.css'],
            ['files', 'static/vendor/jetbrains-mono/files', /-wght-normal\.woff2$/],
        ],
    },
];

const LICENSE_NAMES = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENSE-MIT'];

function copy(from, to, only) {
    if (!existsSync(from)) {
        throw new Error(`Missing ${from}. Run \`npm ci\` first.`);
    }
    mkdirSync(dirname(to), { recursive: true });
    const filter = only ? (src) => statSync(src).isDirectory() || only.test(src) : undefined;
    cpSync(from, to, { recursive: true, filter });
}

// Start clean so a library removed from the list disappears from the repo.
rmSync(join(ROOT, VENDOR_DIR), { recursive: true, force: true });

for (const { pkg, dir, files } of LIBRARIES) {
    const pkgDir = join(ROOT, 'node_modules', pkg);
    for (const [from, to, only] of files) {
        copy(join(pkgDir, from), join(ROOT, to), only);
    }
    // Ship each library's licence next to it (not served: the static route
    // only serves an allow-list of file extensions).
    const license = LICENSE_NAMES.find((name) => existsSync(join(pkgDir, name)));
    if (license) {
        copy(join(pkgDir, license), join(ROOT, VENDOR_DIR, dir || pkg, license));
    }
    console.log(`vendored ${pkg}`);
}
