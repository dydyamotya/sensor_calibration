import logging
import pyqtgraph as pg

from misc import colors_for_lines

logger = logging.getLogger(__name__)

class OneView:
    def __init__(
        self, plot_item: pg.PlotItem, logy: bool = False, sensor_number: int = 12
    ):
        self.sensor_number = sensor_number
        self.plot_item = plot_item
        self.plot_item.setLogMode(y=logy)
        self.emphasized_lines = []

        self.legend = pg.LegendItem(
            offset=(-10, 10),
            labelTextColor=pg.mkColor("#FFFFFF"),
            brush=pg.mkBrush(pg.mkColor("#111111")),
        )

        self.legend.setParentItem(self.plot_item)
        self.plot_item.showGrid(x=True, y=True)

        self.plot_data_items = [
            self.plot_item.plot([0], [0], name=f"Sensor {i + 1}")
            for i in range(self.sensor_number)
        ]

        for idx, (plot_data_item, color) in enumerate(
            zip(self.plot_data_items, colors_for_lines)
        ):
            plot_data_item.setPen(pg.mkPen(pg.mkColor(color), width=2))
            plot_data_item.setCurveClickable(True)
            plot_data_item.sigClicked.connect(self.line_clicked)
            self.legend.addItem(plot_data_item, f"Sensor {idx + 1}")

    def line_clicked(self, line):
        logger.debug("Line clicked")
        if line in self.emphasized_lines:
            line.setShadowPen(pg.mkPen(None))
            self.emphasized_lines.remove(line)
        else:
            line.setShadowPen(pg.mkPen(pg.mkColor("#666666"), width=8))
            self.emphasized_lines.append(line)

    def clear(self):
        self.legend.clear()
        for idx, plot_item_data in enumerate(self.plot_data_items):
            plot_item_data.setData(x=[], y=[])
            if idx < self.sensor_number:
                plot_item_data.setVisible(True)
                self.legend.addItem(plot_item_data, f"Sensor {idx + 1}")
            else:
                plot_item_data.setVisible(False)
        self.legend.update()
        self.plot_item.update()

    def plot_data(self, xs, ys):
        for plot_item, line in zip(
            self.plot_data_items,
            ys,
        ):
            plot_item.setData(x=xs, y=line)

    def set_visible_lines_by_flags(self, flags):
        for flag, plot_line in zip(flags, self.plot_data_items):
            plot_line.setVisible(flag)
        self.plot_item.update()
        self.legend.update()

    def set_sensor_number(self, sensor_number: int):
        self.sensor_number = sensor_number
