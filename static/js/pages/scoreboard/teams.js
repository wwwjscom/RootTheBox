$(document).ready(function() {
  window.scoreboard_ws = new WebSocket(wsUrl() + "/scoreboard/wsocket/pause_score");
        
  if ($("#timercount_hidescoreboard").length > 0) {
      window.RTB.countdown.startFromServer({
            target: "#timercount_hidescoreboard"
        });
      scoreboard_ws.onmessage = function(event) {
          if (event.data !== "pause") {
              location.reload();
          }
      }
  } else {
      if ($("#timercount").length > 0) {
        window.RTB.countdown.startFromServer({
            target: "#timercount"
        });
      }
      scoreboard_ws.onmessage = function(event) {
          if (event.data === "pause") {
              location.reload();
          }
      }
  }
  $("#page_count").on('change', function() {
    document.location.href = "/teams?count=" + this.value + "&page=1";
  });
});

