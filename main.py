import tkinter as tk
from tkinter import ttk

import numpy as np
from scipy.optimize import curve_fit

from sensor_system import MS12, MS4


class MS_Uni():
    def __init__(self, sensor_number, port):
        self.sensors_number = sensor_number
        if sensor_number == 4:
            self.ms = MS4(port)
        elif sensor_number == 12:
            self.ms = MS12(port)
        else:
            raise Exception("Wrong port number")

    def send_measurement_range(self, values):
        self.ms.send_measurement_range(values[:self.sensors_number])
        self.ms.recieve_measurement_range_answer()

    def full_request(self, values):
        return self.ms.full_request(values[:self.sensors_number], self.ms.REQUEST_U)[0]


rs = np.array([5e8, 1e8, 1e7, 1e6, 5.1e4])
r4_str_values = ["100 kOhm", "1.1 MOhm", "11.1 MOhm"]

r4_combobox_dict = dict(zip(r4_str_values, (1e5, 1.1e6, 1.11e7)))
r4_range_dict = dict(zip(r4_str_values, (1, 2, 3)))

window = tk.Tk()
window.title("Sensor calibrator")

r4_label = tk.Label(master=window, text="Сопротивление сравнения:")
r4_variable = tk.StringVar(master=window)
r4_label.grid(column=0, row=0)
r4_combobox = ttk.Combobox(master=window,
                           values=tuple(r4_combobox_dict.keys()),
                           state="readonly",
                           textvariable=r4_variable)
r4_combobox.set(tuple(r4_combobox_dict.keys())[0])
r4_combobox.grid(column=1, row=0)

sensor_label = tk.Label(master=window, text="Номер сенсора")
sensor_label.grid(column=0, row=1)
sensor_values = tuple(range(1, 13))
sensor_variable = tk.IntVar(master=window)
sensor_combobox = ttk.Combobox(master=window,
                               values=sensor_values,
                               state="readonly",
                               textvariable=sensor_variable)
sensor_combobox.set(1)
sensor_combobox.grid(column=1, row=1)

com_port_label = tk.Label(master=window, text="COM Port:")
com_port_label.grid(column=0, row=2)
com_port_variable = tk.StringVar(master=window)
com_port_entry = tk.Entry(master=window, textvariable=com_port_variable)
com_port_entry.grid(column=1, row=2)

r_labels_str = tuple(map("{:1.2e}".format, rs))
r_labels = tuple(tk.Label(master=window, text=label) for label in r_labels_str)
u_variables = tuple(tk.DoubleVar(master=window, value=0) for i in range(len(r_labels_str)))
entries = dict(
    zip(r_labels_str, (tk.Entry(master=window, textvariable=u_variables[i]) for i in range(len(r_labels_str)))))


def get_func(index):
    def measure_u():
        print(f"{com_port_variable.get()}, {r4_variable.get()}, {sensor_variable.get()}")
        ms = MS_Uni(sensor_number=4, port=com_port_variable.get())
        ms.send_measurement_range((r4_range_dict[r4_variable.get()],) * 12)
        answer = ms.full_request((0,) * 12)
        try:
            u_variables[index].set(answer[sensor_variable.get()-1])
        except IndexError:
            print("No sensor there")

    return measure_u


buttons = dict(zip(r_labels_str,
                   (tk.Button(master=window, text="Получить U", command=get_func(i)) for i in
                    range(len(r_labels_str)))))

for idx, (label, entry, button) in enumerate(zip(r_labels, entries.values(), buttons.values())):
    label.grid(column=0, row=idx + 3)
    entry.grid(column=1, row=idx + 3)
    button.grid(column=3, row=idx + 3)


def click_calc_button():
    k = 4.068

    def f(u, rs1, rs2):
        r4 = r4_combobox_dict[r4_variable.get()]
        return (rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4

    x = tuple(u_variables[i].get() for i in range(len(r_labels_str)))
    y = rs
    popt, pcov = curve_fit(f, x, y, p0=(3.004, 1.991))
    print(popt, pcov)


calc_button = tk.Button(master=window, command=click_calc_button)
calc_button.grid(column=0, row=8)

window.mainloop()
