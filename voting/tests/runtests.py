import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'voting.tests.settings'

from django.test.simple import DjangoTestSuiteRunner

runner = DjangoTestSuiteRunner(verbosity=9)
failures = runner.run_tests(None)
if failures:
    sys.exit(failures)
