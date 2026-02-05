/* assets/drag.js */
document.addEventListener("DOMContentLoaded", function () {
    // Check every 1s if the card exists, then attach the dragger
    const intervalId = setInterval(function () {
        const card = document.getElementById("instructions-card");
        if (card && !card.classList.contains("js-draggable")) {
            makeElementDraggable(card);
            card.classList.add("js-draggable");
            // Optional: clear interval if you never expect the card to be re-created
            // clearInterval(intervalId);
        }
    }, 1000);

    function makeElementDraggable(elmnt) {
        var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

        // Use the header as the "handle" if it exists
        var header = elmnt.querySelector(".card-header");
        var handle = header || elmnt;

        handle.style.cursor = "move";

        // --- MOUSE EVENTS (Desktop) ---
        handle.onmousedown = dragMouseDown;

        // --- TOUCH EVENTS (Mobile) ---
        handle.addEventListener('touchstart', dragTouchStart, {passive: false});

        // -----------------------------
        // MOUSE LOGIC
        // -----------------------------
        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            // Get startup position
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        function elementDrag(e) {
            e = e || window.event;
            e.preventDefault();
            // Calculate new position
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            // Set element position
            elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
            elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
        }

        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }

        // -----------------------------
        // TOUCH LOGIC
        // -----------------------------
        function dragTouchStart(e) {
            // e.preventDefault(); // Optional: prevents scrolling page while touching header
            var touch = e.touches[0];
            pos3 = touch.clientX;
            pos4 = touch.clientY;

            document.addEventListener('touchend', closeTouchDrag, {passive: false});
            document.addEventListener('touchmove', elementTouchDrag, {passive: false});
        }

        function elementTouchDrag(e) {
            // PREVENT DEFAULT is critical here to stop the screen from scrolling
            // instead of the card moving
            if (e.cancelable) e.preventDefault();

            var touch = e.touches[0];

            // Calculate new position
            pos1 = pos3 - touch.clientX;
            pos2 = pos4 - touch.clientY;
            pos3 = touch.clientX;
            pos4 = touch.clientY;

            // Set element position
            elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
            elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
        }

        function closeTouchDrag() {
            document.removeEventListener('touchend', closeTouchDrag);
            document.removeEventListener('touchmove', elementTouchDrag);
        }
    }
});