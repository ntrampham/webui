from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.conf import settings
from django.contrib.auth.views import logout_then_login
from django.shortcuts import HttpResponse
from django.urls import path, re_path

from aw.config.hardcoded import LOGIN_PATH
from aw.utils.http import ui_endpoint_wrapper
from aw.views.settings import urlpatterns_settings
from aw.views.job import urlpatterns_jobs


def _local_iframe(_path: str, title: str) -> str:
    return ('<iframe width="100%" height="100%" marginheight="0" marginwidth="0" frameborder="0" '
            f'scrolling="auto" src="{_path}" title="{title}"></iframe>')


@login_required
@ui_endpoint_wrapper
def admin(request) -> HttpResponse:
    return render(request, status=200, template_name='fallback.html', context={
        'content': _local_iframe('/_admin/', title='Admin')
    })


@login_required
@ui_endpoint_wrapper
def api_docs(request) -> HttpResponse:
    return render(request, status=200, template_name='fallback.html', context={
        'content': _local_iframe('/api/_docs', title='API Docs')
    })


@login_required
@ui_endpoint_wrapper
def not_implemented(request) -> HttpResponse:
    return render(request, status=404, template_name='fallback.html', context={'content': 'Not yet implemented'})


@ui_endpoint_wrapper
def catchall(request) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    return redirect(LOGIN_PATH)


@login_required
@ui_endpoint_wrapper
def logout(request) -> HttpResponse:
    return logout_then_login(request)


urlpatterns_ui = [
    path('ui/admin/', admin),
    path('ui/api_docs', api_docs),
]
urlpatterns_ui += urlpatterns_jobs
urlpatterns_ui += urlpatterns_settings
urlpatterns_ui += [
    path('ui/', not_implemented),
    re_path(r'^ui/*', not_implemented),
]
