/* Copy-to-clipboard buttons (team code) */
$(document).ready(function() {
    $("[data-copy-target]").click(function() {
        var button = $(this);
        var text = $(button.data("copy-target")).text().trim();
        navigator.clipboard.writeText(text).then(function() {
            button.html('<i class="fa fa-check"></i> Copied');
        });
    });
});
