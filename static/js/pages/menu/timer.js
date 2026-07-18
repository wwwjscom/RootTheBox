/*
 * Nav bar game countdown.
 *
 * Display only. The client never decides the game is over and never asks
 * the server to stop it - at zero this just writes EXPIRED. The redirect
 * is driven by the game_stopped push handled in libs/notifier.js.
 *
 * New values arrive over the websocket when an admin sets or clears the
 * timer, so nothing here polls the server.
 */
$(document).ready(function() {

    var el = $("#nav-countdown");
    if (el.length === 0) {
        return; // admin menu, or logged out
    }

    var running = null;

    var WARNING_MS = 5 * 60 * 1000;
    var CRITICAL_MS = 60 * 1000;

    // Orange under 5 minutes, red under 1 minute
    function recolor(remaining) {
        el.removeClass("countdown-warning countdown-critical");
        if (remaining < CRITICAL_MS) {
            el.addClass("countdown-critical");
        } else if (remaining <= WARNING_MS) {
            el.addClass("countdown-warning");
        }
    }

    function show(seconds) {
        if (running !== null) {
            running.stop();
            running = null;
        }
        el.removeClass("countdown-warning countdown-critical");
        if (seconds === null || seconds === undefined) {
            el.hide();
            return;
        }
        el.show();
        running = window.RTB.countdown.start({
            target: "#nav-countdown-value",
            distanceMs: parseFloat(seconds) * 1000,
            onTick: recolor
        });
    }

    // Presence of the attribute means a countdown is active. Deliberately
    // not $.is(":visible") - that is false whenever the responsive nav is
    // collapsed, which would stop the countdown ever starting on mobile.
    var initial = el.data("remaining-seconds");
    if (initial !== undefined && initial !== null && initial !== "") {
        show(initial);
    }

    // Admin set, extended, or cleared the countdown
    window.RTB.onCountdown = show;

});
