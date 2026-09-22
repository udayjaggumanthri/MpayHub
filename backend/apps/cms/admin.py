from django.contrib import admin

from apps.cms import models as cms_models

admin.site.register(cms_models.CmsProviderConfig)
admin.site.register(cms_models.CmsEntitlement)
admin.site.register(cms_models.CmsAgentProfile)
admin.site.register(cms_models.CmsWallet)
admin.site.register(cms_models.CmsTransaction)
