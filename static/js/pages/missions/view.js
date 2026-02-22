$(document).ready(function() {
    barcolor();
    levelTimer();
});

function formatDuration(totalSeconds) {
    // Mirror box-page timer formatting for consistency across mission screens.
    var safeSeconds = Math.max(0, parseInt(totalSeconds, 10) || 0);
    var hours = Math.floor(safeSeconds / 3600);
    var minutes = Math.floor((safeSeconds % 3600) / 60);
    var seconds = safeSeconds % 60;
    if (hours > 0) {
        return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
    }
    return String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
}

function levelTimer() {
    // Each level row carries its own timer state in data attributes.
    $("[data-level-submission-timer=1]").each(function() {
        var timerEl = $(this);
        var started = String(timerEl.data("level-submission-timer-started")) === "true";
        var remaining = parseInt(timerEl.data("level-submission-timer-remaining"), 10) || 0;
        var valueEl = timerEl.find(".level-submission-timer-value");

        if (!started) {
            // Timer only begins after first mission-entry confirmation.
            return;
        }

        valueEl.text(formatDuration(remaining));
        if (remaining <= 0) {
            timerEl.removeClass("alert-info").addClass("alert-error");
            if (timerEl.find(".level-submission-timer-expired-msg").length === 0) {
                timerEl.append('<span class="level-submission-timer-expired-msg"> - Expired. You can still view mission details but cannot submit flags.</span>');
            }
            return;
        }

        var timerInterval = setInterval(function() {
            remaining -= 1;
            valueEl.text(formatDuration(remaining));
            if (remaining <= 0) {
                clearInterval(timerInterval);
                timerEl.removeClass("alert-info").addClass("alert-error");
                if (timerEl.find(".level-submission-timer-expired-msg").length === 0) {
                    timerEl.append('<span class="level-submission-timer-expired-msg"> - Expired. You can still view mission details but cannot submit flags.</span>');
                }
            }
        }, 1000);
    });
}

function barcolor() {
    $("a[id^=unlock-game-level-button]").click(function() {
        var buyout = $(this).data("buyout");
        var banking = $(this).data("banking");
        $("#unlock-game-level-uuid").val($(this).data("uuid"));
        var description = "Would you like to unlock this level for ";
        if (banking) {
            description += "$" + buyout + "?";
        } else {
            description += buyout + " point(s)";
        }
        $("#description").text(description);
    });

    $("#unlock-game-level-submit").click(function() {
        $("#unlock-game-level-form").submit();
    });
    
    $(".minibar").each(function() {
        if (this.style.width == "100%") {
            $(this).css('background-color', "#00bb00");
            $(this).css('background-image', 'linear-gradient(to bottom,#00bb00,#009900)')
        } else {
            $(this).css('background-color', "#eeee00");
            $(this).css('background-image', 'linear-gradient(to bottom,#eeee00,#b3b300)');
        }
    });
}
