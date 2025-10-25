# backend/artworks/admin_helper.py
from django import forms
from django.contrib import admin
from .models import ReferenceImage  # только то, что реально нужно в этих классах


class PasteImageWidget(forms.ClearableFileInput):
    def __init__(self, *args, **kwargs):
        attrs = kwargs.get("attrs", {})
        attrs.setdefault("accept", "image/*")
        attrs.setdefault("data-paste-target", "1")
        kwargs["attrs"] = attrs
        super().__init__(*args, **kwargs)

    class Media:
        js = ("admin/paste_image.js",)


class ReferenceInlineForm(forms.ModelForm):
    class Meta:
        model = ReferenceImage
        fields = "__all__"
        widgets = {
            "image": PasteImageWidget(),
        }


class ReferenceInline(admin.TabularInline):
    model = ReferenceImage
    form = ReferenceInlineForm
    extra = 1


__all__ = ["PasteImageWidget", "ReferenceInlineForm", "ReferenceInline"]
