import json
from datetime import date, timedelta
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound


class App(object):

    def __init__(self):
        self.url_map = Map(
            [
                Rule("/", endpoint=""),
                Rule("/get_next_debit", endpoint="get_next_debit")
            ]
        )


    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"on_{endpoint}")(request, **values)
        except NotFound:
            return self.error_404()
        except HTTPException as e:
            return e


    def validate_data(self,data):
        """ This function validates the given object with loan information
        Parameter(s):
        -------------
        self - class instance
        data - data object which contains loan information
        Return:
        -------
        Boolean value: true if valid data, otherwise false
        """
        if not (isinstance(data, dict) and 'loan' in data):
            return False
        if not all(key in data['loan'] for key in ["monthly_payment_amount", "payment_due_day", "schedule_type", "debit_start_date", "debit_day_of_week"]):
            return False
        if not (isinstance(data['loan']['monthly_payment_amount'], int)):
            return False
        if data['loan']['payment_due_day'] > 31 and data['loan']['payment_due_day'] < 1:
            return False
        if not (data['loan']['monthly_payment_amount'] and data['loan']['payment_due_day'] and data['loan']['schedule_type'] \
                and data['loan']['debit_start_date'] and data['loan']['debit_day_of_week']):
                return False
        valid_weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        if data['loan']['debit_day_of_week'].lower() not in valid_weekdays:
            return False
        try:
           if valid_weekdays[date.fromisoformat(data['loan']['debit_start_date']).weekday()] != data['loan']['debit_day_of_week'].lower():
               return False
        except:
            return False
        return True


    def on_get_next_debit(self, request):
        body = request.get_json()
        # create response object
        response = {
            'debit': {
                'amount': 0,
                'date': ''
            }
        }
        if self.validate_data(body):
            today = date.today()
            # for testing: if the request contains "today" key, parse it and use that value
            if body.get('today'):
                today = date.fromisoformat(body['today'])
            debit_start_date = date.fromisoformat(body['loan']['debit_start_date'])
            # due_date = today.replace(month=today.month,day=body['loan']['payment_due_day'])
            # if today > due_date:
            #     due_date = today.replace(month=today.month+1,day=body['loan']['payment_due_day'])
            # initially next debit day is the day when debit started
            next_debit_day = debit_start_date
            # increment next_debit_day by 14 days until > today, which gets the next debit day from today
            while next_debit_day <= today:
                next_debit_day = next_debit_day + timedelta(days=14)
            first_debit_day = next_debit_day
            # To calculate the correct payment amount, we need to get the number of debit days in that month
            # the idea is to get the first debit day of that month then count how many debit days there up until next month
            while first_debit_day.day > 14:
                first_debit_day = first_debit_day - timedelta(days=14)
            num_debit_days = 0
            debit_month = first_debit_day.month
            while first_debit_day.month == debit_month:
                first_debit_day = first_debit_day + timedelta(days=14)
                num_debit_days = num_debit_days + 1
            amount = body['loan']['monthly_payment_amount'] // num_debit_days
            response['debit']['amount'] = amount
            response['debit']['date'] = str(next_debit_day)
        else:
            response['message'] = 'Invalid data'

        return Response(json.dumps(response), mimetype='application/json')


    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)


    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app():
    app = App()
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple

    app = create_app()
    run_simple('0.0.0.0', 5000, app, use_debugger=True, use_reloader=True)
