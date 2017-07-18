import json
import requests

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import mail_admins

from dj_elastictranscoder.models import EncodeJob
from dj_elastictranscoder.signals import (
    transcode_onprogress,
    transcode_onerror,
    transcode_oncomplete
)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def endpoint(request):
    """
    Receive SNS notification
    """
    try:
        data = json.loads(request.read().decode('utf-8'))
    except ValueError:
        return HttpResponseBadRequest('Invalid JSON')

    # handle SNS subscription
    if data['Type'] == 'SubscriptionConfirmation':
        subscribe_url = data['SubscribeURL']
        requests.get(subscribe_url)
        subscribe_body = """
        This URL will confirm your subscription with SNS. I've already visited it, but you can too!

        %s """ % subscribe_url

        mail_admins('Please confirm SNS subscription', subscribe_body)
        return HttpResponse('Subscription confirmed')

    #
    try:
        message = json.loads(data['Message'])
    except ValueError:
        assert False, data['Message']

    #
    if message['state'] == 'PROGRESSING':
        job = EncodeJob.objects.get(pk=message['jobId'])
        job.message = 'Progress'
        job.state = 1
        job.save()

        transcode_onprogress.send(sender=None, job=job, message=message)
    elif message['state'] == 'COMPLETED':
        job = EncodeJob.objects.get(pk=message['jobId'])
        job.message = 'Success'
        job.state = 4
        job.save()

        transcode_oncomplete.send(sender=None, job=job, message=message)
    elif message['state'] == 'ERROR':
        job = EncodeJob.objects.get(pk=message['jobId'])
        job.message = message['messageDetails']
        job.state = 2
        job.save()

        transcode_onerror.send(sender=None, job=job, message=message)

    return HttpResponse('Done')
