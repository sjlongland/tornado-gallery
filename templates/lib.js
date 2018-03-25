function getXHR() {
	var httpRequest;
	if (window.XMLHttpRequest) { // Mozilla, Safari, ...
		httpRequest = new XMLHttpRequest();
	} else if (window.ActiveXObject) { // IE
		httpRequest = new ActiveXObject("Microsoft.XMLHTTP");
	}
	return httpRequest;
}

function fetchImage( width, height, rotation ) {
	data = getData();
	xhr = getXHR();
	photo_obj = document.getElementById( 'photoimg' );

	xhr.onreadystatechange = function() {
		if ( xhr.readyState == 4) {
			document.scroll_en = true;
			if ( xhr.status == 200 ) {
				eval( 'data=' + xhr.responseText );
				photo_obj.src = 
					data.uri + '/' + data.photo.resized;
				document.data = data;
			}
		}
		showPopupFor(3000, '<p class="popuptitle">Image Loaded</h4>'
			+'<p class="popupbody">'
			+'The image has been successfully retrieved.</p>');
		document.scroll_en = true;
	};

	/* Cancel any existing timers */
	if ( document.zoom_timer )
		window.clearTimeout( document.zoom_timer );
	
	/* Set a timer to fetch this data after a 3 second delay */
	url = document.location.protocol + "//" 
			+ document.location.hostname
			+ document.location.pathname
			+ '?width=' + width
			+ '&height=' + height
			+ '&quality=' + data.settings.quality
			+ '&rotation=' + rotation
			+ '&json=1';

	document.zoom_timer = window.setTimeout( function() {
		document.scroll_en = false;
		document.zoom_timer = false;
		document.scroll_en = false;
		showPopup('<p class="popuptitle">Loading Image</h4>'
			+'<p class="popupbody">'
			+'The requested image is being generated...'
			+'Please Wait.</p>');
		xhr.open('GET', url );
		xhr.send(null);
	}, 3000 );
}

function setZoom( zoom ) {
	data = getData();

	/* Round zoom to 1% */
	zoom = Math.round( zoom*100 )/100;

	document.zoom = zoom;
	width = Math.round(data.photo.origwidth*zoom);
	height = Math.round(data.photo.origheight*zoom);

	document.getElementById( 'width' ).value = width;
	document.getElementById( 'height' ).value = height;

	photo_obj = document.getElementById( 'photoimg' );
	if ( photo_obj ) {
		photo_obj.width = width;
		photo_obj.height = height;

		/* If the size is bigger than our present image, request a
		 * bigger one from the server. */
		if ( 		( width > data.photo.width ) || 
				( height > data.photo.height ) ) {
			fetchImage( width, height, data.settings.rotation );
		}
	}
	showPopupFor(3000,'<p class="popuptitle">Zoom Image</h4>'
			+'<p class="popupbody">Zoom photo to '+zoom
			+'x magnification.<br />'
			+'Adjust using your mouse\'s scroll wheel then '
			+'wait a moment to see the result.</p>');
}

function resetZoom() {
	data = getData();
	if ( document.scroll_en )
		setZoom( document.defaultZoom );
}

function adjustZoom( amount ) {
	data = getData();
	if ( document.zoom == null )
		document.zoom = data.photo.zoom;
	if ( document.scroll_en )
		setZoom( document.zoom + amount );
}

function showPopup(body) {
	if ( document.popupDiv )
		div	= document.popupDiv;
	else {
		div	= document.popupDiv
			= document.createElement('div');

		div.style.position='absolute';
		div.style.right='0px';
		div.style.top='0px';
		div.style.width='30em';
		div.style.height='100px';
		div.style.backgroundColor='#ccc';
		div.style.color='black';
		div.style.borderStyle='dotted';
		div.style.borderColor='black';
		div.style.borderWidth='2px';
		div.style.visibility='hidden';
		document.body.appendChild( div );
	}
	div.innerHTML = body;
	div.style.visibility='visible';
}

function showPopupFor(duration, body) {
	showPopup( body );
	if ( document.popup_timer )
		window.clearTimeout( document.popup_timer );
		
	document.popup_timer = window.setTimeout( function() {
		hidePopup();
	}, duration);
}

function hidePopup() {
	document.popupDiv.style.visibility='hidden';
}

function setRotation( angle ) {
	data = getData();

	/* Display a preview */
	preview = document.location.protocol + "//" 
			+ document.location.hostname
			+ data.CGI.ScriptName
			+ '/.rotate_preview'
			+ '?gallery=' + data.gallery.name
			+ '&photo=' + data.photo.name
			+ '&rotation=' + angle;

	if ( preview == document.rotationPreview )
		return;

	showPopup('<img alt="preview" src="'+preview
			+'" width="100" height="100" align="right" />'
			+'<p class="popuptitle">Rotate Photo</p>'
			+'<p class="popupbody">Rotate photo by '+angle
			+' degrees.<br />'
			+'Adjust using your mouse\'s scroll wheel then '
			+'wait a moment to see the result.</p>');

	/* Schedule actual image fetch */
	fetchImage( data.photo.width, data.photo.height, angle );
	rotatefield = document.getElementById( 'rotate' );
	if ( rotatefield ) {
		rotatefield.value = angle;
	}
	document.rotationPreview = preview;
	document.rotation = angle;
}

function adjustRotation(amount) {
	data = getData();
	setRotation( parseFloat(document.rotation) + amount );
}

function wheelHandler( delta ) {
	pan=Math.round(document.getElementById('wheelPan').value);
	zoom=Math.round(document.getElementById('wheelZoom').value)/100;
	angle=parseFloat(document.getElementById('wheelRotate').value);

	if ( document.getElementById('wheelActionZoom').checked )
		if ( document.scroll_en )
			adjustZoom( delta * zoom );
	if ( document.getElementById('wheelActionHPan').checked )
		window.scrollBy( -delta*pan, 0 );
	if ( document.getElementById('wheelActionVPan').checked )
		window.scrollBy( 0, -delta*pan );

	if ( document.getElementById('wheelActionRotate').checked )
		if ( document.scroll_en )
			adjustRotation( -delta*angle );
}
document.scroll_en = true;

function toggleadj() {
	if ( document.adjpanel ) {
		document.getElementById('controls').appendChild(document.adjpanel);
		delete( document.adjpanel );
	} else {
		document.adjpanel = document.getElementById('adjpanel');
		document.getElementById('controls').deleteRow(2);
	}
}
