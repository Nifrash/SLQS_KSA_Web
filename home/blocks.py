"""Homepage-specific editable StreamField blocks.

All existing Phase 2 block types are inherited, so previously authored sections
continue to render after the redesign.
"""
from wagtail import blocks
from wagtail.images.blocks import ImageBlock

from cms_pages.blocks import PageStreamBlock


class ValueItem(blocks.StructBlock):
    label = blocks.CharBlock(max_length=65)
    detail = blocks.CharBlock(required=False, max_length=125)


class ValuesStrip(blocks.StructBlock):
    items = blocks.ListBlock(ValueItem(), min_num=1, max_num=5)

    class Meta:
        template = "home/blocks/values_strip.html"
        icon = "list-ul"
        label = "Values ribbon"
        group = "Homepage sections"


class IntroStory(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=80)
    title = blocks.CharBlock(max_length=180)
    body = blocks.RichTextBlock(features=["h3", "bold", "italic", "link", "ul", "ol"])
    image = ImageBlock(required=False, help_text="Optional. Upload and choose an image; otherwise an architectural illustration is used.")
    image_position = blocks.ChoiceBlock(
        choices=[("right", "Image on right"), ("left", "Image on left")], default="right"
    )
    button_label = blocks.CharBlock(required=False, max_length=55)
    page = blocks.PageChooserBlock(required=False, help_text="Link to an existing Wagtail page.")
    external_url = blocks.URLBlock(required=False, help_text="Alternatively, paste a full https:// URL.")

    class Meta:
        template = "home/blocks/intro_story.html"
        icon = "image"
        label = "Image and editorial story"
        group = "Homepage sections"


class ServiceCard(blocks.StructBlock):
    kicker = blocks.CharBlock(required=False, max_length=60)
    title = blocks.CharBlock(max_length=95)
    description = blocks.TextBlock(max_length=320)
    image = ImageBlock(required=False, help_text="Optional photo or illustration")
    page = blocks.PageChooserBlock(required=False)
    external_url = blocks.URLBlock(required=False)


class ServicesGrid(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=80)
    title = blocks.CharBlock(max_length=170)
    description = blocks.TextBlock(required=False, max_length=500)
    cards = blocks.ListBlock(ServiceCard(), min_num=1, max_num=6)

    class Meta:
        template = "home/blocks/services_grid.html"
        icon = "grip"
        label = "Professional services / cards"
        group = "Homepage sections"


class GalleryImage(blocks.StructBlock):
    image = ImageBlock()
    caption = blocks.CharBlock(required=False, max_length=125)


class PhotoGallery(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=80)
    title = blocks.CharBlock(max_length=170)
    description = blocks.TextBlock(required=False, max_length=400)
    photos = blocks.ListBlock(GalleryImage(), min_num=1, max_num=8)

    class Meta:
        template = "home/blocks/photo_gallery.html"
        icon = "image"
        label = "Photo gallery"
        group = "Homepage sections"


class EventsFeed(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=80)
    title = blocks.CharBlock(max_length=170)
    description = blocks.TextBlock(required=False, max_length=350)

    class Meta:
        template = "home/blocks/events_feed.html"
        icon = "date"
        label = "Live upcoming events"
        group = "Homepage sections"


class NewsFeed(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=80)
    title = blocks.CharBlock(max_length=170)
    description = blocks.TextBlock(required=False, max_length=350)

    class Meta:
        template = "home/blocks/news_feed.html"
        icon = "doc-full"
        label = "Latest published news"
        group = "Homepage sections"


class JoinBanner(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=80)
    title = blocks.CharBlock(max_length=170)
    description = blocks.TextBlock(required=False, max_length=440)
    button_label = blocks.CharBlock(max_length=65, default="Become a member")
    image = ImageBlock(required=False)

    class Meta:
        template = "home/blocks/join_banner.html"
        icon = "group"
        label = "Membership call to action"
        group = "Homepage sections"


class HomeStreamBlock(PageStreamBlock):
    values_strip = ValuesStrip()
    intro_story = IntroStory()
    services_grid = ServicesGrid()
    photo_gallery = PhotoGallery()
    events_feed = EventsFeed()
    news_feed = NewsFeed()
    join_banner = JoinBanner()

    class Meta:
        label = "SLQS Homepage Sections"
