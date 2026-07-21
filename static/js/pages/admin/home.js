$(document).ready(function() {

    window.RTB.countdown.startFromServer({
        target: "#timercount",
        onExpire: function() {
            location.reload();
        }
    });

    $("#start-game-button").click(function() {
        $("#start-game").val("true");
        $("#start-game-form").submit();
    });

    $("#stop-game-button").click(function() {
        $("#start-game").val("false");
        $("#start-game-form").submit();
    });

    $("#suspend-registration-button").click(function() {
        $("#suspend-registration").val("true");
        $("#start-game-form").submit();
    });

    $("#resume-registration-button").click(function() {
        $("#suspend-registration").val("false");
        $("#start-game-form").submit();
    });

    $("#resume-scoreboard-button").click(function() {
        $("#countdown-timer").val("false");
        $("#start-game-form").submit();
    });

    if ($("#automatic-ban").val() === "true") {
        $("#automatic-ban-enable-icon").removeClass("fa-square-o");
        $("#automatic-ban-enable-icon").addClass("fa-check-square-o");
    } else {
        $("#automatic-ban-disable-icon").removeClass("fa-square-o");
        $("#automatic-ban-disable-icon").addClass("fa-check-square-o");
        $("#threshold-size").prop('disabled', true);
    }

    $(".ban-ip-button").click(function() {
        $("#ban-ip").val($(this).data("ip"));
        $("#ban-ip-form").submit();
    });

    $(".clear-ip-button").click(function() {
        $("#clear-ip").val($(this).data("ip"));
        $("#clear-ip-form").submit();
    });

    function updateTimerModeUI() {
        var isAbsolute = $("input[name=timer_mode]:checked").val() === "absolute";
        $("#timer-hours, #timer-minutes").prop("disabled", isAbsolute);
        $("#timer-absolute").prop("disabled", !isAbsolute);
    }

    $("input[name=timer_mode]").change(updateTimerModeUI);

    $("#timer-modal").on("show", function() {
        $("#timer-form")[0].reset();
        updateTimerModeUI();
    });

    $("#timer-submit").click(function() {
        if ($("input[name=timer_mode]:checked").val() === "absolute") {
            var absoluteValue = $("#timer-absolute").val();
            if (!absoluteValue) {
                return;
            }
            $("#timer-absolute-epoch").val(Math.floor(new Date(absoluteValue).getTime() / 1000));
        }
        $("#timer-form").submit();
    });

    $("#message-submit").click(function() {
        $("#message-form").submit();
    });

    /* Enable/disable buttons */
    $("#automatic-ban-enable").click(function() {
        $("#automatic-ban").val("true");
        $("#automatic-ban-enable-icon").removeClass("fa-square-o");
        $("#automatic-ban-enable-icon").addClass("fa-check-square-o");
        $("#automatic-ban-disable-icon").removeClass("fa-check-square-o");
        $("#automatic-ban-disable-icon").addClass("fa-square-o");
        $("#threshold-size").prop('disabled', false);
    });

    $("#automatic-ban-disable").click(function() {
        $("#automatic-ban").val("false");
        $("#automatic-ban-disable-icon").removeClass("fa-square-o");
        $("#automatic-ban-disable-icon").addClass("fa-check-square-o");
        $("#automatic-ban-enable-icon").removeClass("fa-check-square-o");
        $("#automatic-ban-enable-icon").addClass("fa-square-o");
        $("#threshold-size").prop('disabled', true);
    });

});

