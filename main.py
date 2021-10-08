import numpy as np
from scipy.optimize import curve_fit
from serial.tools.list_ports import comports

from sensor_system import MS12, MS4

from PySide2 import QtWidgets, QtCore
from pyqtgraph import PlotWidget

rs = np.array([5e8, 1e8, 1e7, 1e6, 1e5, 5.1e4])
r4_str_values = ["100 kOhm", "1.1 MOhm", "11.1 MOhm"]
r4_combobox_dict = dict(zip(r4_str_values, (1e5, 1.1e6, 1.11e7)))
r4_range_dict = dict(zip(r4_str_values, (1, 2, 3)))

r_labels_str = tuple(map("{:1.2e}".format, rs))


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


class OneSensorFrame(tk.Frame):
    def __init__(self, master, setting, *args, **kwargs):
        super(OneSensorFrame, self).__init__(master=master, *args, **kwargs)
        self.settings = settings
        com_port_variable, sensor_number_variable = self.settings.get_variables()

        r4_label = tk.Label(master=self, text="Сопротивление сравнения:")
        r4_variable = tk.StringVar(master=self)
        r4_label.grid(column=0, row=0)
        r4_combobox = ttk.Combobox(master=self,
                                   values=tuple(r4_combobox_dict.keys()),
                                   state="readonly",
                                   textvariable=r4_variable)
        r4_combobox.set(tuple(r4_combobox_dict.keys())[0])
        r4_combobox.grid(column=1, row=0)

        sensor_label = tk.Label(master=self, text="Номер сенсора")
        sensor_label.grid(column=0, row=1)
        sensor_values = tuple(range(1, 13))
        sensor_variable = tk.IntVar(master=self)
        sensor_combobox = ttk.Combobox(master=self,
                                       values=sensor_values,
                                       state="readonly",
                                       textvariable=sensor_variable)
        sensor_combobox.set(1)
        sensor_combobox.grid(column=1, row=1)

        r_labels = tuple(tk.Label(master=self, text=label) for label in r_labels_str)
        u_variables = tuple(tk.DoubleVar(master=self, value=0) for i in range(len(r_labels_str)))
        entries = dict(
            zip(r_labels_str, (tk.Entry(master=self, textvariable=u_variables[i]) for i in range(len(r_labels_str)))))

        def get_func(index):
            def measure_u():
                print(f"{com_port_variable.get()}, {r4_variable.get()}, {sensor_variable.get()}")
                ms = MS_Uni(sensor_number=sensor_number_variable.get(), port=com_port_variable.get())
                ms.send_measurement_range((r4_range_dict[r4_variable.get()],) * 12)
                answer = ms.full_request((0,) * 12)
                try:
                    u_variables[index].set(answer[sensor_variable.get() - 1])
                except IndexError:
                    print("No sensor there")

            return measure_u

        buttons = dict(zip(r_labels_str,
                           (tk.Button(master=self, text="Получить U", command=get_func(i)) for i in
                            range(len(r_labels_str)))))

        for idx, (label, entry, button) in enumerate(zip(r_labels, entries.values(), buttons.values())):
            label.grid(column=0, row=idx + 3)
            entry.grid(column=1, row=idx + 3)
            button.grid(column=3, row=idx + 3)

        results_var = tk.StringVar(master=self)

        def click_calc_button():
            k = 4.068

            def f(u, rs1, rs2):
                r4 = r4_combobox_dict[r4_variable.get()]
                return (rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4

            x = tuple(u_variables[i].get() for i in range(len(r_labels_str)))
            y = rs
            popt, _ = curve_fit(f, x, y, p0=(3.004, 1.991))
            results_var.set(str(popt))

        calc_button = tk.Button(master=self, command=click_calc_button, text="Calc Coeffs")
        calc_button.grid(column=0, row=8)

        results_label = tk.Label(master=self, textvariable=results_var)
        results_label.grid(column=1, row=8, columnspan=2)


class Variable:
    def __init__(self, master, text, row, var_type, values):
        label = tk.Label(master=master, text=text)
        label.grid(column=0, row=row)
        self.variable = var_type(master=master)
        combobox = ttk.Combobox(master=master,
                                values=values,
                                textvariable=self.variable)
        combobox.grid(column=1, row=row)
        try:
            self.variable.set(values[0])
        except IndexError:
            pass


    def get(self):
        return self.variable.get()


class CopyableEntries(tk.Frame):
    def __init__(self, *args, master=None, columns=1, rows=1, **kwargs):
        super(CopyableEntries, self).__init__(master, *args, **kwargs)

        self.columns = tuple(range(columns))
        self.rows = tuple(range(rows))
        self.entries = dict(
            zip(self.rows, (dict(zip(self.columns, ((None, None),) * len(self.columns))),) * len(self.rows)))
        for column in self.columns:
            for row in self.rows:
                variable = tk.StringVar(self)
                entry = tk.Entry(self, textvariable=variable)
                entry.grid(column=column, row=row)
                self.entries[row][column] = (entry, variable)


class EquipmentSettings:
    def __init__(self, master_of_widgets):
        avaliable_comports = tuple(map(lambda x: x.device, comports()))
        self.intra_frame = tk.Frame(master_of_widgets)

        self.com_port = Variable(self.intra_frame, "COM Port:", 0, tk.StringVar, avaliable_comports)
        self.sensor_number = Variable(self.intra_frame, "Sensor number:", 1, tk.IntVar, (4, 12))
        self.intra_frame.grid(column=0, row=0)

    def get_variables(self):
        return self.com_port, self.sensor_number


window = tk.Tk()
window.title("Sensor calibrator")

settings = EquipmentSettings(window)

frame_1 = OneSensorFrame(window, settings)
frame_1.grid(column=2, row=0)
frame_2 = OneSensorFrame(window, settings)
frame_2.grid(column=3, row=0)

window.mainloop()
