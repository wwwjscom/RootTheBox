var skills_chart;
/* Highcharts code */
$(document).ready(function() {
    /* Skill Chart */
    if ($("#spider_skills").length > 0) {
        skill_chart = new Highcharts.Chart({
            chart: {
                renderTo: 'spider_skills',
                plotBackgroundColor: null,
                plotBorderWidth: null,
                plotShadow: false,
                backgroundColor:'transparent',
                polar: true,
                type: 'line',
                marginTop: 20
            },
            title: {
                text: $("#spider_skills").data("name") || null,
            },
            colors: ['#22b5e8'],
            credits: { enabled: false },
            tooltip: {
                shared: true,
                pointFormat: '<span style="color:{series.color}">{series.name}: <b>{point.y:,.0f}</b><br/>'
            },    
            xAxis: {
                categories: "",
                tickmarkPlacement: 'on',
                lineWidth: 0,
                gridLineColor: '#253041',
                labels: { style: { color: '#8a97a8', fontSize: '12px' } }
            },
            yAxis: {
                gridLineInterpolation: 'polygon',
                gridLineColor: '#253041',
                lineWidth: 0,
                min: 0,
                labels: { enabled: false }
            },
            legend: {
                enabled: false,
                align: 'right',
                verticalAlign: 'top',
                y: 70,
                layout: 'vertical'
            },
            series: [{
                name: 'Skill Progress',
                type: 'area',
                data: [5,6,8],
                pointPlacement: 'on'
            }],
        });
    }
});

/* Update code */
$(document).ready(function() {
    if ($("#spider_skills").length > 0) {
        skill_chart.xAxis[0].setCategories($.parseJSON(categories));
        /* Update Graph */
        $.get("/scoreboard/ajax/skills?uuid=" + $("#spider_skills").data("uuid"), function(skillvalues) {
            skill_chart.series[0].setData($.parseJSON(skillvalues), true);
        });
    }
});

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
