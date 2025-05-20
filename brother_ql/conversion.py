#!/usr/bin/env python

import logging
import datetime

from PIL import Image
import PIL.ImageOps, PIL.ImageChops

from brother_ql.devicedependent import ENDLESS_LABEL, DIE_CUT_LABEL, ROUND_DIE_CUT_LABEL, PTOUCH_ENDLESS_LABEL
from brother_ql.devicedependent import label_type_specs, right_margin_addition
from brother_ql import BrotherQLUnsupportedCmd
from brother_ql.image_trafos import filtered_hsv
from brother_ql.raster import BrotherQLRaster

logger = logging.getLogger(__name__)

logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

def preprocess_image(im, label_specs, qlr, options):
    """
    画像の前処理（ラスタライズ化）を行う関数。
    options: dictで、red, dither, rotate, dpi_600, dots_printable, device_pixel_width, right_margin_dots, threshold などを含む
    戻り値: (im, black_im, red_im)
    """
    red = options.get('red', False)
    dither = options.get('dither', False)
    rotate = options.get('rotate', 'auto')
    dpi_600 = options.get('dpi_600', False)
    dots_printable = options['dots_printable']
    device_pixel_width = options['device_pixel_width']
    right_margin_dots = options['right_margin_dots']
    threshold = options['threshold']

    black_im = None
    red_im = None

    if im.mode.endswith('A'):
        bg = Image.new("RGB", im.size, (255,255,255))
        bg.paste(im, im.split()[-1])
        im = bg
    elif im.mode == "P":
        im = im.convert("RGB" if red else "L")
    elif im.mode == "L" and red:
        im = im.convert("RGB")

    if dpi_600:
        dots_expected = [el*2 for el in dots_printable]
    else:
        dots_expected = dots_printable

    if label_specs['kind'] in (ENDLESS_LABEL, PTOUCH_ENDLESS_LABEL):
        if rotate not in ('auto', 0):
            im = im.rotate(rotate, expand=True)
        if dpi_600:
            im = im.resize((im.size[0]//2, im.size[1]))
        if im.size[0] != dots_printable[0]:
            hsize = int((dots_printable[0] / im.size[0]) * im.size[1])
            im = im.resize((dots_printable[0], hsize), Image.LANCZOS)
            if im.size[0] < device_pixel_width:
                new_im = Image.new(im.mode, (device_pixel_width, im.size[1]), (255,)*len(im.mode))
                new_im.paste(im, (device_pixel_width-im.size[0]-right_margin_dots, 0))
                im = new_im
    elif label_specs['kind'] in (DIE_CUT_LABEL, ROUND_DIE_CUT_LABEL):
        # 1. auto回転判定
        if rotate == 'auto':
            # dots_expectedが縦長で画像が横長なら90度回転
            if dots_expected[0] < dots_expected[1] and im.size[0] > im.size[1]:
                im = im.rotate(90, expand=True)
            # dots_expectedが横長で画像が縦長なら-90度回転（必要なら）
            elif dots_expected[0] > dots_expected[1] and im.size[0] < im.size[1]:
                im = im.rotate(-90, expand=True)
        elif rotate != 0:
            im = im.rotate(rotate, expand=True)
        # 2. サイズチェック＆リサイズ
        if im.size[0] != dots_expected[0] or im.size[1] != dots_expected[1]:
            logger.info(f"[DEBUG] 画像リサイズ: {im.size} → ({dots_printable[0]})")
            input_ratio = im.size[0] / im.size[1]
            expected_ratio = dots_expected[0] / dots_expected[1]
            ratio_tolerance = 0.01
            if abs(input_ratio - expected_ratio) / expected_ratio < ratio_tolerance:
                im = im.resize(dots_expected, Image.LANCZOS)
            else:
                raise ValueError("Bad image dimensions: %s. Expecting: %s." % (im.size, dots_expected))
        if dpi_600:
            im = im.resize((im.size[0]//2, im.size[1]))
        new_im = Image.new(im.mode, (device_pixel_width, dots_expected[1]), (255,)*len(im.mode))
        new_im.paste(im, (device_pixel_width-im.size[0]-right_margin_dots, 0))
        im = new_im

    if red:
        filter_h = lambda h: 255 if (h <  40 or h > 210) else 0
        filter_s = lambda s: 255 if s > 100 else 0
        filter_v = lambda v: 255 if v >  80 else 0
        red_im = filtered_hsv(im, filter_h, filter_s, filter_v)
        red_im = red_im.convert("L")
        red_im = PIL.ImageOps.invert(red_im)
        red_im = red_im.point(lambda x: 0 if x < threshold else 255, mode="1")
        filter_h = lambda h: 255
        filter_s = lambda s: 255
        filter_v = lambda v: 255 if v <  80 else 0
        black_im = filtered_hsv(im, filter_h, filter_s, filter_v)
        black_im = black_im.convert("L")
        black_im = PIL.ImageOps.invert(black_im)
        black_im = black_im.point(lambda x: 0 if x < threshold else 255, mode="1")
        black_im = PIL.ImageChops.subtract(black_im, red_im)
    else:
        im = im.convert("L")
        im = PIL.ImageOps.invert(im)
        if dither:
            im = im.convert("1", dither=Image.FLOYDSTEINBERG)
        else:
            im = im.point(lambda x: 0 if x < threshold else 255, mode="1")
    return im, black_im, red_im

def add_print_page(qlr, im, black_im, red_im, label_specs, hq, cut, peeler,is_last, is_first, compress, dpi_600, red, tape_size, feed_margin):
    qlr.clear()
    try:
        qlr.add_switch_mode()
    except BrotherQLUnsupportedCmd:
        pass
    if is_first:
        qlr.add_status_information()

    # ここにTDの場合は「媒体情報追加コマンド」を
    # qlr.add_device_information()

    if label_specs['kind'] in (DIE_CUT_LABEL, ROUND_DIE_CUT_LABEL):
        qlr.mtype = 0x0B
        qlr.mwidth = tape_size[0]
        qlr.mlength = tape_size[1]
    elif label_specs['kind'] in (ENDLESS_LABEL, ):
        qlr.mtype = 0x0A
        qlr.mwidth = tape_size[0]
        qlr.mlength = 0
    elif label_specs['kind'] in (PTOUCH_ENDLESS_LABEL, ):
        qlr.mtype = 0x00
        qlr.mwidth = tape_size[0]
        qlr.mlength = 0
    qlr.pquality = int(hq)
    qlr.add_media_and_quality(im.size[1])
    try:
        if cut and is_last:
            qlr.add_mode_setting(autocut=True, peeler=peeler)
            qlr.add_cut_every(1)
        else:
            qlr.add_mode_setting(autocut=False, peeler=peeler)
    except BrotherQLUnsupportedCmd:
        pass
    try:
        qlr.dpi_600 = dpi_600
        qlr.cut_at_end = True
        qlr.two_color_printing = True if red else False
        qlr.add_expanded_mode()
    except BrotherQLUnsupportedCmd:
        pass
    qlr.add_wait(0)
    qlr.add_margins(feed_margin)
    if qlr.compression_support:
        qlr.add_compression(compress)
    if red:
        qlr.add_raster_data(black_im, red_im)
    else:
        qlr.add_raster_data(im)
    qlr.add_print(last_page=is_last)
    return qlr.data

def _rasterize_images(qlr: BrotherQLRaster, images, label, queue: bool = False, copies: int = 1, **kwargs):
    """
    copies: 同じ画像を何枚印刷するか（効率化用）
    """
    label_specs = label_type_specs[label]
    dots_printable = label_specs['dots_printable']
    right_margin_dots = label_specs['right_margin_dots']
    right_margin_dots += right_margin_addition.get(qlr.model, 0)
    device_pixel_width = qlr.get_pixel_width()
    cut = kwargs.get('cut', True)
    peeler = kwargs.get('peeler', False)
    dither = kwargs.get('dither', False)
    compress = kwargs.get('compress', False)
    red = kwargs.get('red', False)
    rotate = kwargs.get('rotate', 'auto')
    if rotate != 'auto': rotate = int(rotate)
    dpi_600 = kwargs.get('dpi_600', False)
    hq = kwargs.get('hq', True)
    threshold = kwargs.get('threshold', 70)
    threshold = 100.0 - threshold
    threshold = min(255, max(0, int(threshold/100.0 * 255)))
    if red and not qlr.two_color_support:
        raise BrotherQLUnsupportedCmd('Printing in red is not supported with the selected model.')
    qlr.add_invalidate()
    qlr.add_initialize()
    page_data = []
    logger.info(f"Rasterizing {len(images)} pages (copies={copies})")

    # 画像リストを作成
    if len(images) == 1 and copies > 1:
        images_to_process = [images[0]] * copies
    else:
        images_to_process = images

    for i, image in enumerate(images_to_process):
        if isinstance(image, Image.Image):
            im = image
        else:
            try:
                im = Image.open(image)
            except OSError:
                raise NotImplementedError("The image argument needs to be an Image() instance, the filename to an image, or a file handle.")
        options = dict(red=red, dither=dither, rotate=rotate, dpi_600=dpi_600, dots_printable=dots_printable, device_pixel_width=device_pixel_width, right_margin_dots=right_margin_dots, threshold=threshold)
        im, black_im, red_im = preprocess_image(im, label_specs, qlr, options)
        is_last = (i == len(images_to_process) - 1)
        is_first = (i == 0)
        tape_size = label_specs['tape_size']
        feed_margin = label_specs['feed_margin']
        data = add_print_page(qlr, im, black_im, red_im, label_specs, hq, cut, peeler, is_last, is_first, compress, dpi_600, red, tape_size, feed_margin)
        page_data.append(data)

    if queue:
        return page_data
    else:
        data = b''.join(page_data)
        return data

def convert(qlr: BrotherQLRaster, images, label, **kwargs):
    # Legacy method with no queue support, returns a single bytes object
    qlr.add_invalidate()
    qlr.add_initialize()
    # qlr.add_status_information()
    setup_data = qlr.data
    qlr.clear()

    copies = kwargs.pop('copies', 1)
    page_data = _rasterize_images(qlr, images, label, copies=copies, **kwargs)
    return setup_data + page_data

def queue_convert(qlr: BrotherQLRaster, images, label, **kwargs):
    # Queue conversion method, init handled by the print queue class
    # Returns a list of bytes
    kwargs['queue'] = True
    page_data = _rasterize_images(qlr, images, label, **kwargs)
    return page_data
