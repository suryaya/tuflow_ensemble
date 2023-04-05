import unittest
import os
import pandas as pd
from tuflow_ensemble import tuflow_ensemble
import pathlib

wd = pathlib.Path(__file__).parent.resolve()

sample_data = os.path.join(wd, "sample_data")


class testParsePoCSV(unittest.TestCase):
    # This test checks that result csv file is being parsed as a dataframe
    # correctly.
    def test_parse_po_csv(self):
        expected_output = pd.read_pickle(os.path.join(wd, "df_parse_po_csv.pickle"))
        input_csv = os.path.join(sample_data, "Example_010.0Y_10m_tp01_001_PO.csv")
        actual_output = tuflow_ensemble.parse_po_csv(input_csv)
        pd.testing.assert_frame_equal(expected_output, actual_output)


class testParseStormName(unittest.TestCase):
    # This test checks that storm names are being parsed into storm
    # frequency, duration and temp pattern correctly.
    def test_parse_storm_name(self):
        storm_name = "Example-Catchment_0.5EY_360m_tp07_no-blockages_001_PO.csv"
        expected_tuple = ("0.5ey", "360m", "tp07")
        actual_tuple = tuflow_ensemble._parse_run_id(storm_name)
        self.assertEqual(expected_tuple, actual_tuple)


if __name__ == "__main__":
    unittest.main()
