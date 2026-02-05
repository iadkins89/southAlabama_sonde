/* assets/fix_map.js */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        resizeListener: function(value) {
            setTimeout(function() {
                window.dispatchEvent(new Event('resize'));
            }, 500);
            return window.dash_clientside.no_update;
        }
    }
});

/* Auto-trigger resize on page load to fix Leaflet not centering on a sensor properly*/
document.addEventListener("DOMContentLoaded", function() {
    setTimeout(function() {
        window.dispatchEvent(new Event('resize'));
    }, 500);
});