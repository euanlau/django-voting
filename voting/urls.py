from django.conf.urls import *
from voting.views import VoteView

urlpatterns = patterns('',
    url(r"^vote/(?P<app_label>[\w\.-]+)/(?P<model_name>\w+)/"\
        "(?P<object_id>\d+)/(?P<direction>up|down|clear)/$",
        VoteView.as_view(),
        name="voting_vote"
    ),
)
