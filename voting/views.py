from django.core.exceptions import ObjectDoesNotExist
from django.db.models import get_model
from django.http import Http404, HttpResponse, HttpResponseBadRequest, \
    HttpResponseRedirect
from django.contrib.auth.views import redirect_to_login
from django.template import loader, RequestContext
from django.utils import simplejson
from django.views.generic.base import View, ContextMixin, TemplateResponseMixin

from braces.views import JSONResponseMixin, AjaxResponseMixin
from voting.models import Vote

VOTE_DIRECTIONS = (('up', 1), ('down', -1), ('clear', 0))

class VoteObjectMixin(ContextMixin):
    """
    Generic object vote mixin.
    """
    pk_url_kwarg = 'object_id'
    slug_url_kwarg = 'slug'
    slug_field = 'slug'
    app_label_url_kwarg = 'app_label'
    model_name_url_kwarg = 'model_name'
    directon_url_kwarg = 'direction'
    context_object_name = 'object'
    post_vote_redirect = None

    def get_model(self):
        """
        Returns the model of the object that is being voted

        If the model is not specified explicity, it uses the app_label and model_name
        in the URL
        of a model class and calls ``vote_on_object`` view.
        Returns HTTP 400 (Bad Request) if there is no model matching the app_label
        and model_name.
        """
        model = self.kwargs.get('model', None)
        if model:
            return model

        app_label = self.kwargs.get(self.app_label_url_kwarg, None)
        model_name = self.kwargs.get(self.model_name_url_kwarg, None)

        if not app_label or not model_label:
            raise AttributeError('Generic vote view must be called with '
                                 'app_label and model_label ')

        model = get_model(app_label, model_name)
        if not model:
            raise AttributeError('Model %s.%s does not exist' % (
                app_label, model_name))

        return model

    def get_object(self):
        """
        Returns the object the view is displaying.

        By default this requires `object_id` or `slug` argument
        in the URLconf, but subclasses can override this to return any object.
        """
        model = self.get_model()
        slug = self.kwargs.get(self.slug_url_kwarg, None)
        slug_field = self.get_slug_field()
        object_id = self.kwargs.get(self.pk_url_kwarg, None)


        # Look up the object to be voted on
        lookup_kwargs = {}
        if object_id:
            lookup_kwargs['%s__exact' % model._meta.pk.name] = object_id
        elif slug and slug_field:
            lookup_kwargs['%s__exact' % slug_field] = slug
        else:
            raise AttributeError('Generic vote view must be called with either '
                                 'object_id or slug and slug_field.')
        try:
            obj = model._default_manager.get(**lookup_kwargs)
        except ObjectDoesNotExist:
            raise AttributeError('No %s found for %s.' %
                                 (model._meta.app_label, lookup_kwargs))
        return obj

    def vote_on_object(self, obj):
        """
        Record vote on the object by the current user

        Vote direction [up/clear/down] can be specified in the URLconf.
        If not, it toggles between up/clear instead.
        """
        direction = self.kwargs.get(self.directon_url_kwarg, None)
        user = self.request.user

        if direction:
            try:
                vote = dict(VOTE_DIRECTIONS)[direction]
            except KeyError:
                raise AttributeError("'%s' is not a valid vote type." % direction)

            v = Vote.objects.record_vote(obj, user, vote)
        else:
            v = Vote.objects.toggle(obj, user)

        return v

    def get_score(self, obj):
        """
        Get the current score of the given object
        """
        return Vote.objects.get_score(obj)

    def get_slug_field(self):
        """
        Get the name of a slug field to be used to look up by slug.
        """
        return self.slug_field

    def get_context_object_name(self, obj):
        """
        Get the name to use for the object.
        """
        if self.context_object_name:
            return self.context_object_name
        elif isinstance(obj, models.Model):
            return obj._meta.object_name.lower()
        else:
            return None

    def get_context_data(self, **kwargs):
        """
        Insert the single object into the context dict.
        """
        context = {}
        #context_object_name = self.get_context_object_name(self.object)
        #if context_object_name:
        #    context[context_object_name] = self.object
        context.update(kwargs)
        return context


class VoteView(TemplateResponseMixin, JSONResponseMixin, AjaxResponseMixin, VoteObjectMixin, View):
    """
    Generic object vote View.

    This handles both ajax and regular html request.

    The given template will be used to get the score if this view is
    fetched using GET; vote registration will only be performed if this
    view is POSTed.
    """

    content_type = "text/html"

    def get_content_type(self):
        # for render_json_response
        return "applcation/json"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        score = self.get_score(self.object)
        context = self.get_context_data(score=score, **kwargs)
        return self.render_to_response(context)

    def get_ajax(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            score = self.get_score(self.object)
            context = self.get_context_data(score=score)
        except AttributeError, err:
            context = {
                'success' : False,
                'error': err
            }
        return self.render_json_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.vote_on_object(self.object)

        if post_vote_redirect is not None:
            next = post_vote_redirect
        elif 'next' in self.request.GET:
            next = self.request.GET['next']
        elif hasattr(self.object, 'get_absolute_url'):
            if callable(getattr(obj, 'get_absolute_url')):
                next = self.object.get_absolute_url()
            else:
                next = self.object.get_absolute_url
        else:
            raise AttributeError('Generic vote view must be called with either '
                                 'post_vote_redirect, a "next" parameter in '
                                 'the request, or the object being voted on '
                                 'must define a get_absolute_url method or '
                                 'property.')

        return HttpResponseRedirect(next)

    def post_ajax(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            vote = self.vote_on_object(self.object)
            score = self.get_score(self.object)
            context = self.get_context_data(score=score, vote=vote, success=True)
        except AttributeError, err:
            context = {
                'success' : False,
                'error': err
            }
        return self.render_json_response(context)
