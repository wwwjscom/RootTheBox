$(document).ready(function() {
    var reader = new commonmark.Parser({smart: true});
    var writer = new commonmark.HtmlRenderer({safe: true});
    // Single client-side lock switch used by all submission controls on this page.
    var submissionsLocked = false;

    function formatDuration(totalSeconds) {
        // Match backend display format and clamp negatives for expired timers.
        var safeSeconds = Math.max(0, parseInt(totalSeconds, 10) || 0);
        var hours = Math.floor(safeSeconds / 3600);
        var minutes = Math.floor((safeSeconds % 3600) / 60);
        var seconds = safeSeconds % 60;
        if (hours > 0) {
            return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
        }
        return String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
    }

    function setSubmissionsLocked(locked) {
        submissionsLocked = locked;
        if (!locked) {
            return;
        }
        // Expired timer state: visually warn and block all flag submission interactions.
        $("#level-submission-timer").removeClass("alert-info").addClass("alert-error");
        if ($("#level-submission-timer-expired-msg").length === 0) {
            $("#level-submission-timer").append('<span id="level-submission-timer-expired-msg"> - Time has expired for this level. You can still view content but cannot submit flags.</span>');
        }
        $("#capture-text-flag-box-token, #capture-text-flag-box-submit, #capture-text-flag-submit, #capture-choice-flag-submit, #capture-file-flag-submit, #flag-token, #flag-file").prop("disabled", true);
        $("a[id^=capture-file-flag-button], a[id^=capture-text-flag-button], a[id^=capture-choice-flag-button]").addClass("disabled");
        $("#capture-file-flag-modal, #capture-text-flag-modal, #capture-choice-flag-modal").modal("hide");
    }

    /* Markdown */
    $(".markdown").each(function() {
        var parsed = reader.parse($(this).text());
        var formatted = writer.render(parsed).trim();
        $(this).html(formatted.replaceAll("<a href=", '<a target="_blank" href='));
    });

    if ($("#level-submission-timer").length > 0) {
        // Start/continue countdown from server-provided remaining seconds.
        var remainingSeconds = parseInt($("#level-submission-timer").data("remaining-seconds"), 10) || 0;
        $("#level-submission-timer-value").text(formatDuration(remainingSeconds));
        if ($("#level-submission-timer").data("expired") === true || remainingSeconds <= 0) {
            setSubmissionsLocked(true);
        } else {
            var timerInterval = setInterval(function() {
                remainingSeconds -= 1;
                $("#level-submission-timer-value").text(formatDuration(remainingSeconds));
                if (remainingSeconds <= 0) {
                    setSubmissionsLocked(true);
                    clearInterval(timerInterval);
                }
            }, 1000);
        }
    }

    /* Flags */
    $("#capture-file-flag-modal").on('shown.bs.modal', function () {
        $("#flag-file").focus()
    });

    $("a[id^=capture-file-flag-button]").click(function(e) {
        // Prevent opening submission modals once the level timer has expired.
        if (submissionsLocked) {
            e.preventDefault();
            return false;
        }
        $("#capture-file-flag-uuid").val($(this).data("uuid"));
    });

    $("#capture-file-flag-submit").click(function() {
        if (submissionsLocked) {
            return false;
        }
        $("#capture-file-flag-form").submit();
    });

    $("#capture-text-flag-modal").on('shown.bs.modal', function () {
        $("#flag-token").focus()
    });

    $("a[id^=capture-text-flag-button]").click(function(e) {
        // Prevent opening submission modals once the level timer has expired.
        if (submissionsLocked) {
            e.preventDefault();
            return false;
        }
        $("#capture-text-flag-uuid").val($(this).data("uuid"));
    });

    $("#capture-text-flag-submit").click(function() {
        if (submissionsLocked) {
            return false;
        }
        $("#capture-text-flag-form").submit();
    });

    $("a[id^=capture-choice-flag-button]").click(function(e) {
        // Prevent opening submission modals once the level timer has expired.
        if (submissionsLocked) {
            e.preventDefault();
            return false;
        }
        $("#capture-choice-flag-uuid").val($(this).data("uuid"));
        $("#choiceinput").empty();
        var choices = $(this).data("choices");
        for (choice in choices) {
            $("#choiceinput").append('<div><input required name="multichoice" type="radio" style="margin-top: 0;" value="' + choices[choice].replace(/"/g, "__quote__") + '" />&nbsp;&nbsp;' + choices[choice] + "</div><br/>");
        }
    });

    $("#capture-choice-flag-submit").click(function() {
        if (submissionsLocked) {
            return false;
        }
        $("#choice-flag-token").val($('input[name=multichoice]:checked').val());
        $("#capture-choice-flag-form").submit();
    });

    $("#capture-text-flag-box-form, #capture-text-flag-form, #capture-choice-flag-form, #capture-file-flag-form").submit(function() {
        // Final guard so stale tabs cannot submit after expiration.
        return !submissionsLocked;
    });

    $(".flag-expand").click(function() {
        var isHovered = $('.playstory').filter(function() {
            return $(this).is(":hover");
        });
        if ($('.playstory').length === 0 || isHovered.length === 0) {
            $(this).next(".flag-collapse").toggle();
            $(this).next().next(".flag-collapse").toggle();
        }
    });

    $(".showflag").click(function() {
        $("#showknownname").text($(this).data("name"));
        $("#showknownflag").text("Flag: " + $(this).data("flag"));
    });

    /* Hints */
    $("a[id^=purchase-hint-button]").click(function() { 
        $("#purchase-hint-uuid").val($(this).data("uuid"));
        var price = $(this).data("price");
        hintdialog(price);
    });
    $("a[id^=purchase-flag-hint-button]").click(function() {
        //index is different on flags
        $("#purchase-hint-uuid").val($(this).data("uuid"));
        var price = $(this).data("price");
        hintdialog(price);
    });
    $("#purchase-hint-submit").click(function() {
        $("#purchase-hint-form").submit();
    });

    function hintdialog(price) {
        var bank = $("#hintbanking").val();
        if (price === "0") {
            $("#purchase-hint-text").text("This hint is free.  Would you like to take it?");
        } else if (bank == 'true') {
            $("#purchase-hint-text").text("Would you like to purchase this hint for $"+price+"?");
        } else {
            $("#purchase-hint-text").text("Would you like to take this hint for a deduction of "+price+" points?");
        }
    }
    $('td').on('mouseenter mouseleave', function(e) {
        //Allows the hover background to include the flag hints
        var tbody = $(this).closest("tbody");
        if (tbody.hasClass("flagbody")) {
            if ($(this).hasClass("hidehovercolor")) {
                tbody.css('background-color', $(this).next().css('background-color'));
            } else {
                tbody.css('background-color', $(this).css('background-color'));
            }
        }
    });
    $('tbody').on('mouseleave', function(e) {
        $(this).css('background-color','');
    });

    if($('#box-materials').length > 0)
    {
        var data = {'_xsrf': getCookie("_xsrf")}
        var subdir = $('#box-materials').data("subdir");
        $.post('/materials/' + subdir + "/", data, function(response) {
            $('#box-materials-tree').jstree({
                'core' : {
                    'themes' : { name : 'default-dark' },
                    'data' : $.parseJSON(response)["children"]
                }
            });
        });
    }
    if ( window.history.replaceState ) {
        location.hash = location.hash;
        window.history.replaceState( null, null, window.location.href );
    }
});
