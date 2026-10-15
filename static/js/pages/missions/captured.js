// A bold "*** LABEL ***" banner as wide as the terminal (one column spare so
// it never wraps), with the label centred.
function banner(term, label) {
    var stars = Math.max(6, term.cols() - 1 - label.length - 2);
    var left = Math.floor(stars / 2);
    return "[[b;;]" + "*".repeat(left) + " " + label + " " + "*".repeat(stars - left) + "]";
}

function text_animation(term) {
    var index = 0;
    var flag = $('#flag').val();
    var reward = $('#reward').val();
    var msg = $('#capture-message').val();
    var banking = $('#banking').val();
    var intro_frames = [];
    if (flag.length > 0) {
        intro_frames.push("I have received the '" + flag + "' information.");
        intro_frames.push("  ");
        if (reward.length > 0) {
            if (banking === "$") {
                intro_frames.push("This is acceptable and I have transferred $" + reward + " to your account.", " ");
            } else {
                intro_frames.push("This is acceptable and I have added " + reward + " points to your score.", " ");
            }
        }
    }
    if (msg.toString() !== "" && msg.toString() !== "None") {
        msgsplit = msg.toString().split("\n\n")
        for (x in msgsplit) {
            intro_frames.push(msgsplit[x], " ");
        }
    }
    term.echo(banner(term, "BEGIN SECURE COMMUNIQUE") + "\n");

    function display(term, index) {
        term.echo(intro_frames[index], {keepWords: true});
        index += 1;
        if (index < intro_frames.length) {
            setTimeout(display, 2000, term, index);
        } else {
            term.echo(banner(term, "END OF TRANSMISSION"));
            term.resume();
        }
    }
    setTimeout(display, 1500, term, index);
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
        if ($(this).val().length > 0) {
            window.location = '/user/missions/boxes?uuid=' + htmlEncode($(this).val());
        } else {
            window.location = '/user/missions';
        }
        
    });
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