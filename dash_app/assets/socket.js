// Ensure dash_clientside exists
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.clientside = window.dash_clientside.clientside || {};

// Add the update_store function
window.dash_clientside.clientside.update_store = function(msg) {
    // trigger a callback from the hidden div update
    return msg || window.dash_clientside.no_update;
};

// Initialize Socket
function initSocket() {
    if (typeof io !== 'undefined') {
        const socket = io();

        socket.on("connect", () => {
            console.log("✅ Socket.IO connected");
        });

        socket.on("sensor_update", (data) => {
            // Every sensor's packets reach every browser, so only react to the one on screen
            const sensorOnScreen = new URLSearchParams(window.location.search).get("sensor");
            if (data.sensor !== sensorOnScreen) return;

            console.log("📡 Sensor update received:", data);
            dash_clientside.set_props("live-sensor-data", { data: data });
        });
    } else {
        setTimeout(initSocket, 100);
    }
}

initSocket();



