$(document).ready(function() {
    data = {'_xsrf': getCookie("_xsrf")}
    subdir = $('#container').data("subdir");
    $.post('/materials' + subdir, data, function(response) {
        $('#container').jstree({
            'core' : {
              'themes' : { name : 'default-dark' },
              'data' : JSON.parse(response)["children"]
            }
        });
    });
});
