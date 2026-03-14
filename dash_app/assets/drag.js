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
            // 1. Calculate how far the mouse moved (Delta)
            let dx = e.clientX - pos3;
            let dy = e.clientY - pos4;

            // 2. Update stored position for the next frame
            pos3 = e.clientX;
            pos4 = e.clientY;

            applyClampedMovement(dx, dy);
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

            let dx = touch.clientX - pos3;
            let dy = touch.clientY - pos4;

            pos3 = touch.clientX;
            pos4 = touch.clientY;

            applyClampedMovement(dx, dy);
        }

        function closeTouchDrag() {
            document.removeEventListener('touchend', closeTouchDrag);
            document.removeEventListener('touchmove', elementTouchDrag);
        }
        function applyClampedMovement(dx, dy) {
            // Get actual on-screen dimensions of the card
            let rect = elmnt.getBoundingClientRect();

            // Get Navbar bottom edge dynamically
            let navbar = document.querySelector('.custom-navbar');
            let minY = navbar ? navbar.getBoundingClientRect().bottom : 0;

            // Use visualViewport for absolute safety on mobile browsers
            let viewHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
            let viewWidth = window.visualViewport ? window.visualViewport.width : window.innerWidth;

            // Calculate exactly how much empty pixel space we have in every direction.
            // Math.max(0, ...) ensures we never calculate negative space if resized.
            let maxMoveUp = Math.max(0, rect.top - minY);
            let maxMoveDown = Math.max(0, viewHeight - rect.bottom);
            let maxMoveLeft = Math.max(0, rect.left);
            let maxMoveRight = Math.max(0, viewWidth - rect.right);

            // Clamp the delta (dx, dy) so it can never exceed the available empty space
            if (dy < 0 && Math.abs(dy) > maxMoveUp) dy = -maxMoveUp;       // Moving Up
            if (dy > 0 && dy > maxMoveDown) dy = maxMoveDown;              // Moving Down
            if (dx < 0 && Math.abs(dx) > maxMoveLeft) dx = -maxMoveLeft;   // Moving Left
            if (dx > 0 && dx > maxMoveRight) dx = maxMoveRight;            // Moving Right

            // Apply the safely clamped delta to the local offset
            elmnt.style.top = (elmnt.offsetTop + dy) + "px";
            elmnt.style.left = (elmnt.offsetLeft + dx) + "px";
        }
    }
});