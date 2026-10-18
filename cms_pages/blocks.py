"""Curated, accessible StreamField blocks for professional SLQS pages.

Editors can choose and reorder these blocks without changing templates.
Use PageChooserBlock for internal links to Wagtail pages where possible.
"""
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageBlock


class SectionHeadingBlock(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=90, help_text="Small heading above the main title")
    title = blocks.CharBlock(max_length=180)
    description = blocks.TextBlock(required=False, max_length=700)

    class Meta:
        icon = "title"
        label = "Section heading"
        template = "cms_pages/blocks/section_heading.html"
        group = "Text & layout"


class ImageTextBlock(blocks.StructBlock):
    image = ImageBlock()
    eyebrow = blocks.CharBlock(required=False, max_length=90)
    title = blocks.CharBlock(max_length=180)
    text = blocks.RichTextBlock(features=["h3", "bold", "italic", "link", "ol", "ul"])
    image_position = blocks.ChoiceBlock(choices=[("left", "Image on left"), ("right", "Image on right")], default="left")

    class Meta:
        icon = "image"
        label = "Image and text"
        template = "cms_pages/blocks/image_text.html"
        group = "Media"


class FeatureCardBlock(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=60)
    title = blocks.CharBlock(max_length=100)
    description = blocks.TextBlock(max_length=350)
    page = blocks.PageChooserBlock(required=False, help_text="Internal Wagtail page (takes priority over external URL)")
    external_url = blocks.URLBlock(required=False)


class CardsBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, max_length=150)
    cards = blocks.ListBlock(FeatureCardBlock(), min_num=1, max_num=6)

    class Meta:
        icon = "grip"
        label = "Feature cards"
        template = "cms_pages/blocks/cards.html"
        group = "Highlights"


class StatisticBlock(blocks.StructBlock):
    value = blocks.CharBlock(max_length=35, help_text="Use verified figures only, e.g. 12+ or 2027")
    label = blocks.CharBlock(max_length=90)


class StatisticsBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, max_length=150)
    stats = blocks.ListBlock(StatisticBlock(), min_num=1, max_num=4)

    class Meta:
        icon = "order"
        label = "Statistics"
        template = "cms_pages/blocks/statistics.html"
        group = "Highlights"


class QuoteBlock(blocks.StructBlock):
    quote = blocks.TextBlock(max_length=900)
    attribution = blocks.CharBlock(required=False, max_length=120)
    role = blocks.CharBlock(required=False, max_length=120)

    class Meta:
        icon = "openquote"
        label = "Quotation"
        template = "cms_pages/blocks/quote.html"
        group = "Text & layout"


class FAQItemBlock(blocks.StructBlock):
    question = blocks.CharBlock(max_length=220)
    answer = blocks.RichTextBlock(features=["bold", "italic", "link", "ol", "ul"])


class FAQBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, max_length=150)
    items = blocks.ListBlock(FAQItemBlock(), min_num=1, max_num=20)

    class Meta:
        icon = "help"
        label = "Frequently asked questions"
        template = "cms_pages/blocks/faq.html"
        group = "Text & layout"


class CallToActionBlock(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, max_length=90)
    title = blocks.CharBlock(max_length=180)
    description = blocks.TextBlock(required=False, max_length=500)
    button_label = blocks.CharBlock(required=False, max_length=65)
    page = blocks.PageChooserBlock(required=False, help_text="Internal Wagtail page; preferred over external URL")
    external_url = blocks.URLBlock(required=False)

    class Meta:
        icon = "link"
        label = "Call to action"
        template = "cms_pages/blocks/call_to_action.html"
        group = "Highlights"


class DocumentLinkBlock(blocks.StructBlock):
    document = DocumentChooserBlock()
    label = blocks.CharBlock(max_length=140)
    description = blocks.TextBlock(required=False, max_length=300)

    class Meta:
        icon = "doc-full"
        label = "Downloadable document"
        template = "cms_pages/blocks/document_link.html"
        group = "Media"


class VideoBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, max_length=140)
    video = EmbedBlock(help_text="Paste a supported provider's video URL (e.g. YouTube)")

    class Meta:
        icon = "media"
        label = "Embedded video"
        template = "cms_pages/blocks/video.html"
        group = "Media"


class TwoColumnBlock(blocks.StructBlock):
    left = blocks.RichTextBlock(features=["h2", "h3", "bold", "italic", "link", "ol", "ul"])
    right = blocks.RichTextBlock(features=["h2", "h3", "bold", "italic", "link", "ol", "ul"])

    class Meta:
        icon = "placeholder"
        label = "Two text columns"
        template = "cms_pages/blocks/two_columns.html"
        group = "Text & layout"


class PageStreamBlock(blocks.StreamBlock):
    heading = SectionHeadingBlock()
    rich_text = blocks.RichTextBlock(
        features=["h2", "h3", "h4", "bold", "italic", "link", "document-link", "ol", "ul"],
        icon="doc-full",
        label="Rich text",
        template="cms_pages/blocks/rich_text.html",
        group="Text & layout",
    )
    image_text = ImageTextBlock()
    cards = CardsBlock()
    statistics = StatisticsBlock()
    quote = QuoteBlock()
    faq = FAQBlock()
    call_to_action = CallToActionBlock()
    document = DocumentLinkBlock()
    video = VideoBlock()
    two_columns = TwoColumnBlock()
    divider = blocks.StaticBlock(
        admin_text="Insert a light divider between sections.",
        template="cms_pages/blocks/divider.html", icon="horizontalrule", group="Text & layout",
    )

    class Meta:
        label = "SLQS Page Sections"
