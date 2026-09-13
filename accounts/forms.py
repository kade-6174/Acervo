from allauth.account.forms import ChangePasswordForm, LoginForm


class AcervoLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["login"].label = "ユーザー名"
        self.fields["password"].label = "パスワード"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class AcervoChangePasswordForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["oldpassword"].label = "現在のパスワード"
        self.fields["oldpassword"].help_text = None
        self.fields["password1"].label = "新しいパスワード"
        self.fields["password2"].label = "新しいパスワード（確認）"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def save(self):
        super().save()
        if self.user.must_change_password:
            self.user.must_change_password = False
            self.user.save(update_fields=["must_change_password"])
