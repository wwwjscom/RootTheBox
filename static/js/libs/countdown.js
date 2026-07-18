/*
 * Shared countdown rendering.
 *
 * Namespaced deliberately: the scoreboard and admin pages each declare
 * their own global setTimer/padDigits, and those files load from
 * {% block header %} which renders after this one - so anything defined
 * here under those names would be silently overwritten.
 */
window.RTB = window.RTB || {};

window.RTB.countdown = (function() {

    function padDigits(number, digits) {
        return Array(Math.max(digits - String(number).length + 1, 0)).join(0) + number;
    }

    // Matches the "Dd Hh MMm SSs" format used by the scoreboard timers
    function format(distance) {
        var days = Math.max(0, Math.floor((distance) / (1000 * 60 * 60 * 24)));
        var hours = Math.max(0, Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)));
        var minutes = Math.max(0, Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)));
        var seconds = Math.max(0, Math.floor((distance % (1000 * 60)) / 1000));

        var text = padDigits(minutes, 2) + "m " + padDigits(seconds, 2) + "s";
        if (hours > 0) {
            text = hours + "h " + text;
        }
        if (days > 0) {
            text = days + "d " + text;
        }
        return text;
    }

    /*
     * Counts `distanceMs` down into `opts.target` (a selector, element or
     * jQuery object), calling `onExpire` once at zero.  Returns a handle
     * with stop(), so a caller can cancel a running countdown when the
     * server sends a new value.
     *
     * Time is measured against an absolute deadline rather than by
     * subtracting a fixed amount per tick.  Ticks are not delivered on
     * schedule - browsers throttle background tabs to as little as one
     * tick a minute, and freeze them outright - so counting ticks loses
     * time permanently and silently.  Reading the clock each paint means a
     * throttled or slept tab simply shows a stale value while hidden and
     * is correct again on its first tick back in the foreground.
     *
     * Only the client's own clock is ever used, so a player whose machine
     * disagrees with the server still sees the right remaining time.
     */
    function start(opts) {
        var target = opts.target;
        var formatter = opts.format || format;
        var deadline = Date.now() + opts.distanceMs;
        var interval = null;
        var expired = false;

        function remaining() {
            return deadline - Date.now();
        }

        // Called with the milliseconds just rendered (0 once expired), so
        // callers can restyle as the deadline approaches
        function notify(ms) {
            if (opts.onTick) {
                opts.onTick(ms);
            }
        }

        function clear() {
            if (interval !== null) {
                clearInterval(interval);
                interval = null;
            }
        }

        function expire() {
            if (expired) {
                return;
            }
            expired = true;
            $(target).text(
                opts.expiredText !== undefined ? opts.expiredText : "EXPIRED"
            );
            clear();
            detach();
            notify(0);
            if (opts.onExpire) {
                opts.onExpire();
            }
        }

        function paint() {
            var ms = remaining();
            if (ms > 0) {
                $(target).text(formatter(ms));
                notify(ms);
            } else {
                expire();
            }
        }

        // A tab that was hidden or asleep is corrected by its next tick
        // anyway; repainting on wake makes that instant rather than up to
        // a second late.
        function onVisible() {
            if (!document.hidden) {
                paint();
            }
        }

        function detach() {
            if (document.removeEventListener) {
                document.removeEventListener("visibilitychange", onVisible);
            }
        }

        paint();
        // An already-expired value must not leave a live interval behind
        if (!expired) {
            interval = setInterval(paint, 1000);
            if (document.addEventListener) {
                document.addEventListener("visibilitychange", onVisible);
            }
        }

        return {
            stop: function() {
                clear();
                detach();
            }
        };
    }

    /*
     * Starts a countdown from the game timer endpoint.
     *
     * The endpoint writes an empty body when no countdown is configured;
     * treating that as a number yields 0, which would render "EXPIRED" on
     * a scoreboard that simply has no timer set.  Guarded here so every
     * caller gets it right.
     */
    function startFromServer(opts) {
        $.get("/scoreboard/ajax/timer", function(seconds) {
            if (seconds === "" || seconds === null || seconds === undefined) {
                return;
            }
            var settings = {};
            for (var key in opts) {
                if (opts.hasOwnProperty(key)) {
                    settings[key] = opts[key];
                }
            }
            settings.distanceMs = parseFloat(seconds) * 1000;
            start(settings);
        });
    }

    return {
        format: format,
        start: start,
        startFromServer: startFromServer
    };

})();
