import os
import datetime
from django.shortcuts import render, redirect
import requests
from django.http import JsonResponse
import json
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from newsapi import NewsApiClient
from requests.api import request

from django.urls import reverse
from django.views.generic import FormView
from django.views.generic import View
from django.views.generic import TemplateView
from paypal.standard.forms import PayPalPaymentsForm

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from .forms import NewUserForm

from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.db.models.query_utils import Q
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes

from .utils import render_to_pdf
from django.template.loader import get_template

from django.contrib import messages
from datetime import date

import reportlab                  # generates reports

# news API from newsapi.org
API_KEY = '8d8d51e07d8d40078290e6f9a8c68ed4'

class DataManager:
    data = []

    def setData(self, d):
        self.data = d

    def getData(self):
        return self.data


# obtaining data from the news API
def news(request):
    date = datetime.datetime(2021, 9, 19)
    oldest = request.GET.get('date')
    category = request.GET.get('category')
    popularity = request.GET.get('popularity')

    if request.method == 'POST':
        qInTitle = request.POST['search']

        url = f'https://newsapi.org/v2/everything?q={qInTitle}&from={oldest}&sortBy={popularity}&apiKey={API_KEY}'
        response = requests.get(url)
        data = response.json()

        articles = data['articles']

    elif category:
        url = f'https://newsapi.org/v2/top-headlines?category={category}&sortBy=relevancy&language=en&apiKey={API_KEY}'
        response = requests.get(url)
        data = response.json()

        articles = data['articles']

    else:
        url = f'https://newsapi.org/v2/top-headlines?country=us&sortBy={popularity}&apiKey={API_KEY}'
        response = requests.get(url)
        data = response.json()

        articles = data['articles']
        uuid = 0
        newData = []
        for article in articles:
            article = {**article, 'uuid': uuid}
            uuid = uuid + 1
            article['source']['id'] = uuid

        data_manager = DataManager()
        data_manager.setData(articles)

    context = {'articles': articles}
    return render(request, 'home.html', context)


def report(request):
    return render(request, 'report.html')


# signup page
def register_request(request):
    if request.method == "POST":
        form = NewUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("citizen_app:news")
        messages.error(
            request, "Unsuccessful registration. Invalid information.")
    form = NewUserForm()

    return render(request=request, template_name='accounts/register.html', context={"register_form": form})


# login page
def login_request(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"You are now logged in as {username}.")
                return redirect("citizen_app:news")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    form = AuthenticationForm()
    return render(request=request, template_name="accounts/login.html", context={"login_form": form})

# logout page


def logout_request(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect("citizen_app:news")


def password_reset_request(request):
    if request.method == "POST":
        password_reset_form = PasswordResetForm(request.POST)
        if password_reset_form.is_valid():
            data = password_reset_form.cleaned_data['email']
            associated_users = User.objects.filter(Q(email=data))
            if associated_users.exists():
                for user in associated_users:
                    subject = "Password Reset Requested"
                    email_template_name = "accounts/password_reset_email.txt"
                    c = {
                        "email": user.email,
                        'domain': '127.0.0.1:8000',
                        'site_name': 'Website',
                        "uid": urlsafe_base64_encode(force_bytes(user.pk)).decode(),
                        "user": user,
                        'token': default_token_generator.make_token(user),
                        'protocol': 'http',
                    }
                    email = render_to_string(email_template_name, c)
                    try:
                        send_mail(subject, email, 'admin@citizendigital.com',
                                  [user.email], fail_silently=False)
                    except BadHeaderError:
                        return HttpResponse('Invalid header found.')
                    messages.success(
                        request, 'A message with reset password instructions has been sent to your inbox.')
                    return redirect("citizen_app:news")
                messages.error(request, 'An invalid email has been entered.')
    password_reset_form = PasswordResetForm()
    return render(request=request, template_name="accounts/password_reset.html", context={"password_reset_form": password_reset_form})

# paypal


class PaypalFormView(FormView):
    template_name = 'paypal_form.html'
    form_class = PayPalPaymentsForm

    def get_initial(self):
        return {
            "business": 'sb-h3r9j8948196@business.example.com',
            "amount": 1.00,
            "currency_code": "USD",
            "item_name": 'Article',
            "invoice": 1234,
            "notify_url": self.request.build_absolute_uri(reverse('paypal-ipn')),
            "return_url": self.request.build_absolute_uri(reverse('paypal-return')),
            "cancel_return": self.request.build_absolute_uri(reverse('paypal-cancel')),
            "lc": 'EN',
            "no_shipping": '1',
        }


class PaypalReturnView(TemplateView):
    template_name = 'paypal_success.html'


class PaypalCancelView(TemplateView):
    template_name = 'paypal_cancel.html'


# report view
class GeneratePdf(View):
    def render_data(request):
        url = f'https://newsapi.org/v2/top-headlines?country=us&apiKey={API_KEY}'
        response = requests.get(url)
        data = response.json()

        articles = data['articles']
        uuid = 0
        newData = []
        for article in articles:
            article = {**article, 'uuid': uuid}
            uuid = uuid + 1
            article['source']['id'] = uuid

        data_manager = DataManager()
        data_manager.setData(articles)

        context = {'articles': articles}

    def get(self, request, *args, **kwargs):
        template = get_template('report.html')
        context = {
            "user": request.user,
        }
        html = template.render(context)
        pdf = render_to_pdf('report.html', context)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            filename = "Report_%s.pdf" % ("12341231")
            content = "inline; filename='%s'" % (filename)
            download = request.GET.get("download")
            if download:
                content = "attachment; filename='%s'" % (filename)
            response['Content-Disposition'] = content
            return response
        return HttpResponse("Not found")


def showReadMore(request, title):
    if request.method == 'GET':
        url = f'https://newsapi.org/v2/everything?q={title}&apiKey={API_KEY}'
        response = requests.get(url)
        data = response.json()
        context = {'data': data['articles'][0]}
        return render(request, 'readmore.html', context)


def report(request):
    today = date.today()
    url = f'https://newsapi.org/v2/top-headlines?country=us&sortBy=relevancy&apiKey={API_KEY}'
    response = requests.get(url)
    data = response.json()

    articles = data['articles']
    uuid = 0
    newData = []
    for article in articles:
        article = {**article, 'uuid': uuid}
        uuid = uuid + 1
        article['source']['id'] = uuid

    data_manager = DataManager()
    data_manager.setData(articles)

    context = {'articles': articles, "user": request.user, "today": today}
    # return redirect("citizen_app:payment")
    return render(request, 'report.html', context)


def payment(request):
    context = {
        "user": request.user
    }
    return render(request, 'payment.html', context)
