#SJL: OAuth 邮箱补充表单，字段由服务端校验，不使用前端值代替业务校验。
from django.contrib.auth.forms import forms
from django.forms import widgets


class RequireEmailForm(forms.Form):
    #SJL: oauthid 使用隐藏字段，服务端仍会按主键查询并校验 OAuthUser 是否存在。
    email = forms.EmailField(label='电子邮箱', required=True)
    oauthid = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super(RequireEmailForm, self).__init__(*args, **kwargs)
        self.fields['email'].widget = widgets.EmailInput(
            attrs={'placeholder': "email", "class": "form-control"})
