// Copy the browser libraries pinned in package.json into the app's static tree.
//
//   npm ci && npm run vendor
//
// The output is committed, so running the app never needs Node. CI reruns
// this script and fails if the committed files differ from the lockfile's
// versions. Never edit the copied files by hand: change the version in
// package.json, run the commands above, and commit the result.
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const VENDOR_DIR = 'static/vendor';

// Each library: npm package, then [source in the package, destination in the
// repo]. Sources may be files or directories. Destinations are under
// static/vendor/ unless there is a reason noted below.
const LIBRARIES = [
    { pkg: 'jquery', files: [['dist/jquery.min.js', 'static/vendor/jquery/jquery.min.js']] },
    { pkg: 'jquery-migrate', files: [['dist/jquery-migrate.min.js', 'static/vendor/jquery-migrate/jquery-migrate.min.js']] },
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
            // The theme system loads theme CSS from static/css/themes/, and the
            // Default theme's file list (stored in the database) names
            // bootstrap.min.css, so it stays at that path.
            ['dist/css/bootstrap.min.css', 'static/css/themes/bootstrap.min.css'],
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
];

const LICENSE_NAMES = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENSE-MIT'];

function copy(from, to) {
    if (!existsSync(from)) {
        throw new Error(`Missing ${from}. Run \`npm ci\` first.`);
    }
    mkdirSync(dirname(to), { recursive: true });
    cpSync(from, to, { recursive: true });
}

// Start clean so a library removed from the list disappears from the repo.
rmSync(join(ROOT, VENDOR_DIR), { recursive: true, force: true });

for (const { pkg, files } of LIBRARIES) {
    const pkgDir = join(ROOT, 'node_modules', pkg);
    for (const [from, to] of files) {
        copy(join(pkgDir, from), join(ROOT, to));
    }
    // Ship each library's licence next to it (not served: the static route
    // only serves an allow-list of file extensions).
    const license = LICENSE_NAMES.find((name) => existsSync(join(pkgDir, name)));
    if (license) {
        copy(join(pkgDir, license), join(ROOT, VENDOR_DIR, pkg, license));
    }
    console.log(`vendored ${pkg}`);
}
