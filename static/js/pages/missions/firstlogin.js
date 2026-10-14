var dialog;
// A bold "*** LABEL ***" banner as wide as the terminal (one column spare so
// it never wraps), with the label centred.
function banner(term, label) {
    var stars = Math.max(6, term.cols() - 1 - label.length - 2);
    var left = Math.floor(stars / 2);
    return "[[b;;]" + "*".repeat(left) + " " + label + " " + "*".repeat(stars - left) + "]";
}

function text_animation(term) {
    var index = 0;
    var intro_frames = $.parseJSON(dialog);

    term.echo(banner(term, "BEGIN SECURE COMMUNIQUE") + "\n");

    function display(term, index) {
        term.echo(intro_frames[index], {keepWords: true});
        index += 1;
        if (index < intro_frames.length) {
            setTimeout(display, 1500, term, index);
        } else {
            term.echo(banner(term, "END OF TRANSMISSION"));
            term.resume();
        }
    }
    setTimeout(display, 2000, term, index);
}

function loading(term) {
    term.clear();
    var count = 0;
    loading_bar = ["|", "/", "-", "\\"];
    message = "\n[[b;;]> Establishing communication channel, please wait...]";

    function display(term, count) {
        term.clear();
        sym = loading_bar[count % loading_bar.length];
        term.echo(message + sym);
        count += 1;
        if (count < 35) {
            setTimeout(display, 100, term, count);
        } else {
            $(".c-glitch").empty();
            term.clear();
            text_animation(term);
        }
    }
    display(term, count);
}

function greetings(term) {
    // Hide the prompt until the transmission ends. Deferred, because jQuery
    // Terminal 2.x resumes itself after onInit returns.
    setTimeout(function() {
        term.pause();
        loading(term);
    }, 0);
}

$(document).ready(function() {
    $("#closebutton").click(function(){
        window.location = '/user';
    });
    /* Update Summary Table */
    $.get("/user/missions/ajax/firstlogin", function(firstlogin) {
        dialog = firstlogin;
        $('#console').terminal({
            /* No commands just animation */
        }, {
            prompt: " > ",
            name: 'console',
            greetings: null,
            tabcompletion: true,
            onInit: function(term) {
                greetings(term);
            },
        });
    });
});
