"""Read an X11 window's own composited pixels without capturing other apps."""

import ctypes
import threading

from PIL import Image


_LOCK = threading.Lock()
_DISPLAY = ctypes.c_void_p
_XID = ctypes.c_ulong


class _Visual(ctypes.Structure):
    _fields_ = [
        ('ext_data', ctypes.c_void_p), ('visualid', _XID),
        ('visual_class', ctypes.c_int), ('red_mask', ctypes.c_ulong),
        ('green_mask', ctypes.c_ulong), ('blue_mask', ctypes.c_ulong),
        ('bits_per_rgb', ctypes.c_int), ('map_entries', ctypes.c_int),
    ]


class _WindowAttributes(ctypes.Structure):
    _fields_ = [
        ('x', ctypes.c_int), ('y', ctypes.c_int),
        ('width', ctypes.c_int), ('height', ctypes.c_int),
        ('border_width', ctypes.c_int), ('depth', ctypes.c_int),
        ('visual', ctypes.POINTER(_Visual)), ('root', _XID),
        ('window_class', ctypes.c_int), ('bit_gravity', ctypes.c_int),
        ('win_gravity', ctypes.c_int), ('backing_store', ctypes.c_int),
        ('backing_planes', ctypes.c_ulong), ('backing_pixel', ctypes.c_ulong),
        ('save_under', ctypes.c_int), ('colormap', _XID),
        ('map_installed', ctypes.c_int), ('map_state', ctypes.c_int),
        ('all_event_masks', ctypes.c_long), ('your_event_mask', ctypes.c_long),
        ('do_not_propagate_mask', ctypes.c_long),
        ('override_redirect', ctypes.c_int), ('screen', ctypes.c_void_p),
    ]


class _XImage(ctypes.Structure):
    # The following prefix is sufficient to read an XImage. Xlib owns the
    # remaining function pointers and frees the full structure itself.
    _fields_ = [
        ('width', ctypes.c_int), ('height', ctypes.c_int),
        ('xoffset', ctypes.c_int), ('format', ctypes.c_int),
        ('data', ctypes.c_void_p), ('byte_order', ctypes.c_int),
        ('bitmap_unit', ctypes.c_int), ('bitmap_bit_order', ctypes.c_int),
        ('bitmap_pad', ctypes.c_int), ('depth', ctypes.c_int),
        ('bytes_per_line', ctypes.c_int), ('bits_per_pixel', ctypes.c_int),
        ('red_mask', ctypes.c_ulong), ('green_mask', ctypes.c_ulong),
        ('blue_mask', ctypes.c_ulong),
    ]


class _XErrorEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_int), ('display', _DISPLAY),
        ('resourceid', _XID), ('serial', ctypes.c_ulong),
        ('error_code', ctypes.c_ubyte), ('request_code', ctypes.c_ubyte),
        ('minor_code', ctypes.c_ubyte),
    ]


_ERROR_HANDLER = ctypes.CFUNCTYPE(
    ctypes.c_int, _DISPLAY, ctypes.POINTER(_XErrorEvent))


def _libraries():
    x11 = ctypes.CDLL('libX11.so.6')
    composite = ctypes.CDLL('libXcomposite.so.1')
    signatures = [
        ('XOpenDisplay', _DISPLAY, [ctypes.c_char_p]),
        ('XCloseDisplay', ctypes.c_int, [_DISPLAY]),
        ('XDefaultRootWindow', _XID, [_DISPLAY]),
        ('XSync', ctypes.c_int, [_DISPLAY, ctypes.c_int]),
        ('XSetErrorHandler', ctypes.c_void_p, [ctypes.c_void_p]),
        ('XGetErrorText', ctypes.c_int,
         [_DISPLAY, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]),
        ('XGetWindowAttributes', ctypes.c_int,
         [_DISPLAY, _XID, ctypes.POINTER(_WindowAttributes)]),
        ('XTranslateCoordinates', ctypes.c_int,
         [_DISPLAY, _XID, _XID, ctypes.c_int, ctypes.c_int,
          ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
          ctypes.POINTER(_XID)]),
        ('XGetImage', ctypes.POINTER(_XImage),
         [_DISPLAY, _XID, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
          ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]),
        ('XDestroyImage', ctypes.c_int, [ctypes.POINTER(_XImage)]),
        ('XFreePixmap', ctypes.c_int, [_DISPLAY, _XID]),
    ]
    for name, result, arguments in signatures:
        function = getattr(x11, name)
        function.restype = result
        function.argtypes = arguments
    composite.XCompositeQueryExtension.restype = ctypes.c_int
    composite.XCompositeQueryExtension.argtypes = [
        _DISPLAY, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    composite.XCompositeNameWindowPixmap.restype = _XID
    composite.XCompositeNameWindowPixmap.argtypes = [_DISPLAY, _XID]
    return x11, composite


def _decode(image, visual):
    if image.bits_per_pixel not in (24, 32):
        raise RuntimeError(f'Unsupported X11 pixel size: {image.bits_per_pixel}')
    byte_count = image.bits_per_pixel // 8
    masks = (image.red_mask or visual.red_mask,
             image.green_mask or visual.green_mask,
             image.blue_mask or visual.blue_mask)
    raw_order = ['X'] * byte_count
    for channel, mask in zip('RGB', masks):
        if not mask:
            raise RuntimeError('X11 window has no RGB visual')
        shift = (mask & -mask).bit_length() - 1
        if mask >> shift != 255 or shift % 8:
            raise RuntimeError(f'Unsupported X11 channel mask: {mask:#x}')
        index = shift // 8
        if image.byte_order:  # MSBFirst
            index = byte_count - 1 - index
        if not 0 <= index < byte_count or raw_order[index] != 'X':
            raise RuntimeError('Invalid X11 RGB visual')
        raw_order[index] = channel
    if (not image.data or image.width <= 0 or image.height <= 0 or
            image.bytes_per_line < image.width * byte_count):
        raise RuntimeError('Invalid X11 image buffer')
    pixels = ctypes.string_at(
        image.data, image.bytes_per_line * image.height)
    return Image.frombytes(
        'RGB', (image.width, image.height), pixels, 'raw',
        ''.join(raw_order), image.bytes_per_line)


def capture_window(window_id, expected_geometry=None):
    """Return the mapped window's own pixels as a new PIL RGB image.

    Requires an active X11 compositor, such as GNOME on Xorg. It works when
    other windows cover the wallpaper, because it reads the window's backing
    pixmap rather than the screen. A disappearing/unmapped window raises
    RuntimeError instead of letting Xlib terminate the calling process.
    If expected_geometry is (x, y, width, height), require the window to occupy
    exactly that rectangle on the root display before capturing it.

    Xlib's error handler is process-wide. Calls here are serialized; callers
    should avoid concurrent direct Xlib work in other threads.
    """
    window = int(window_id, 0) if isinstance(window_id, str) else int(window_id)
    if window <= 0:
        raise ValueError('Expected a positive X11 window ID')
    with _LOCK:
        x11, composite = _libraries()
        display = x11.XOpenDisplay(None)
        if not display:
            raise RuntimeError('Cannot open the X11 display')
        errors = []

        @_ERROR_HANDLER
        def record_error(_display, event):
            errors.append((event.contents.error_code,
                           event.contents.resourceid))
            return 0

        previous = x11.XSetErrorHandler(
            ctypes.cast(record_error, ctypes.c_void_p))
        pixmap = 0
        image = None

        def check_errors():
            x11.XSync(display, 0)
            if errors:
                code, resource = errors[0]
                message = ctypes.create_string_buffer(256)
                x11.XGetErrorText(display, code, message, len(message))
                raise RuntimeError(
                    f'X11 capture failed for {window:#x}: '
                    f'{message.value.decode(errors="replace")} '
                    f'(resource {resource:#x})')

        try:
            event_base, error_base = ctypes.c_int(), ctypes.c_int()
            if not composite.XCompositeQueryExtension(
                    display, ctypes.byref(event_base), ctypes.byref(error_base)):
                raise RuntimeError('XComposite is unavailable')
            attributes = _WindowAttributes()
            success = x11.XGetWindowAttributes(
                display, window, ctypes.byref(attributes))
            check_errors()
            if not success or attributes.map_state != 2:
                raise RuntimeError(f'X11 window {window:#x} is not viewable')
            if not attributes.visual:
                raise RuntimeError('X11 window has no visual')
            if not 0 < attributes.width <= 32768 or not 0 < attributes.height <= 32768:
                raise RuntimeError('Invalid X11 window dimensions')
            if expected_geometry is not None:
                x, y, child = ctypes.c_int(), ctypes.c_int(), _XID()
                translated = x11.XTranslateCoordinates(
                    display, window, x11.XDefaultRootWindow(display), 0, 0,
                    ctypes.byref(x), ctypes.byref(y), ctypes.byref(child))
                check_errors()
                actual = (x.value, y.value, attributes.width, attributes.height)
                if not translated or actual != tuple(expected_geometry):
                    raise RuntimeError('Wallpaper window is not at the selected monitor geometry')
            named_pixmap = composite.XCompositeNameWindowPixmap(display, window)
            check_errors()
            pixmap = named_pixmap
            if not pixmap:
                raise RuntimeError('Cannot name the X11 window backing pixmap')
            # The Composite pixmap includes the window border. Wallpaper
            # windows normally have none; the offset also handles ordinary
            # bordered windows without including their border in the result.
            border = attributes.border_width
            image = x11.XGetImage(
                display, pixmap, border, border,
                attributes.width, attributes.height,
                ctypes.c_ulong(-1).value, 2)  # AllPlanes, ZPixmap
            check_errors()
            if not image:
                raise RuntimeError('Cannot read the X11 window backing pixmap')
            return _decode(image.contents, attributes.visual.contents)
        finally:
            if image:
                x11.XDestroyImage(image)
            if pixmap:
                x11.XFreePixmap(display, pixmap)
            # Keep the temporary error handler alive until pending requests
            # and display teardown finish, then restore the caller's handler.
            x11.XSync(display, 0)
            x11.XCloseDisplay(display)
            x11.XSetErrorHandler(previous)
