import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password, MinimumLengthValidator
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Create the initial instructor once; never reset an existing password.'

    def handle(self, *args, **options):
        username = os.environ.get('INSTRUCTOR_USERNAME', '').strip()
        password = os.environ.get('INSTRUCTOR_PASSWORD', '')
        if not username or not password:
            raise CommandError('Set INSTRUCTOR_USERNAME and INSTRUCTOR_PASSWORD for initial setup.')
        users = get_user_model().objects
        if users.filter(username=username).exists():
            self.stdout.write('Instructor already exists; credentials unchanged.')
            return
        try:
            validate_password(password, password_validators=[
                MinimumLengthValidator(12)
            ])
        except ValidationError:
            raise CommandError('Instructor password must contain at least 12 characters.')
        users.create_user(username=username, password=password)
        self.stdout.write('Instructor created.')
