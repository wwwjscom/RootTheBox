/*
 * bs5-jquery-bridge.js
 *
 * Bootstrap 5 dropped the jQuery plugin API ($.fn.modal, $.fn.popover, ...).
 * Root the Box still drives Bootstrap components imperatively from jQuery in
 * ~88 places (popover init, modal show/hide, tooltip, collapse). Rather than
 * rewrite every call site, this shim re-exposes the handful of jQuery plugin
 * methods we actually use, delegating to Bootstrap 5's native JS API.
 *
 * Declarative usage (data-bs-toggle / data-bs-dismiss) is handled natively by
 * Bootstrap 5 and does NOT go through this file.
 *
 * Load order: after jQuery AND after bootstrap.bundle.min.js.
 */
(function ($, bootstrap) {
    "use strict";
    if (!$ || !bootstrap) {
        return;
    }

    // Map a jQuery plugin name to its Bootstrap 5 component class.
    var COMPONENTS = {
        modal: bootstrap.Modal,
        tooltip: bootstrap.Tooltip,
        popover: bootstrap.Popover,
        collapse: bootstrap.Collapse,
        dropdown: bootstrap.Dropdown,
        tab: bootstrap.Tab,
        alert: bootstrap.Alert,
        toast: bootstrap.Toast,
    };

    // Instance methods that BS5 exposes and that BS2's jQuery API accepted as
    // a string argument, e.g. $(el).modal("show").
    var METHODS = ["show", "hide", "toggle", "dispose", "handleUpdate", "update"];

    function makePlugin(name, Component) {
        return function (config) {
            var arg = arguments.length ? config : undefined;
            return this.each(function () {
                var instance = Component.getOrCreateInstance(this, typeof arg === "object" ? arg : {});
                if (typeof arg === "string" && METHODS.indexOf(arg) !== -1 && typeof instance[arg] === "function") {
                    instance[arg]();
                } else if (arg === undefined || typeof arg === "object") {
                    // BS2 semantics: modal() with no/opts argument opens the modal;
                    // the other components just initialize on creation.
                    if (name === "modal" && typeof instance.show === "function") {
                        instance.show();
                    }
                }
            });
        };
    }

    Object.keys(COMPONENTS).forEach(function (name) {
        var Component = COMPONENTS[name];
        if (Component && !$.fn[name]) {
            $.fn[name] = makePlugin(name, Component);
        }
    });
})(window.jQuery, window.bootstrap);
