/* Source: http://adomas.org/javascript-mouse-wheel/ */
function wheel(event){
	var delta = 0;
	if (!event) /* For IE. */
		event = window.event;
	if (event.wheelDelta) { /* IE/Opera. */
		delta = event.wheelDelta/120;
		if (window.opera)
			delta = -delta;
	} else if (event.detail) { /** Mozilla case. */
		delta = -event.detail/3;
	}
	if (delta)
		wheelHandler(delta);
	if (event.preventDefault)
		event.preventDefault();
	event.returnValue = false;
}

if (window.addEventListener)
	/** DOMMouseScroll is for mozilla. */
	window.addEventListener('DOMMouseScroll', wheel, false);
else
	/** IE/Opera. */
	window.onmousewheel = document.onmousewheel = wheel;
