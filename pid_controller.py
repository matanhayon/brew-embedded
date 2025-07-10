import time

class PIDArduino:
    def __init__(self, sample_time_sec, kp, ki, kd, output_min=0, output_max=100):
        if kp is None or ki is None or kd is None:
            raise ValueError("PID parameters must be specified")
        if float(sample_time_sec) <= 0:
            raise ValueError('sample_time_sec must be greater than 0')

        self.Kp = kp
        self.Ki = ki * sample_time_sec
        self.Kd = kd / sample_time_sec
        self.sample_time = sample_time_sec * 1000  # Convert to milliseconds
        self.output_min = output_min
        self.output_max = output_max
        self.i_term = 0
        self.last_input = 0
        self.last_output = 0
        self.last_calc = 0

    def calc(self, input_value, setpoint):
        now = time.time() * 1000  # Current time in milliseconds

        if (now - self.last_calc) < self.sample_time:
            return self.last_output

        error = setpoint - input_value
        d_input = input_value - self.last_input

        if self.output_min < self.last_output < self.output_max:
            self.i_term += self.Ki * error
            self.i_term = min(self.i_term, self.output_max)
            self.i_term = max(self.i_term, self.output_min)

        p = self.Kp * error
        i = self.i_term
        d = -(self.Kd * d_input)

        self.last_output = p + i + d
        self.last_output = min(self.last_output, self.output_max)
        self.last_output = max(self.last_output, self.output_min)

        self.last_input = input_value
        self.last_calc = now

        return self.last_output
