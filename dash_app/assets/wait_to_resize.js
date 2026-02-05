/* assets/fix_map.js */

// Check if dash_clientside exists, if not create it
window.dash_clientside = window.dash_clientside || {};

// Check if the 'clientside' namespace exists, if not create it
window.dash_clientside.clientside = window.dash_clientside.clientside || {};

// Safely add your function to the namespace
window.dash_clientside.clientside.resizeListener = function(value) {
    setTimeout(function() {
        window.dispatchEvent(new Event('resize'));
    }, 500);
    return window.dash_clientside.no_update;
};

/* Auto-trigger resize on page load to fix Leaflet not centering properly */
document.addEventListener("DOMContentLoaded", function() {
    setTimeout(function() {
        window.dispatchEvent(new Event('resize'));
    }, 500);
});