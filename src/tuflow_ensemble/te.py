import csv
import os
import shutil
import pandas as pd
import re
from matplotlib import pyplot as plt
import seaborn as sns
from tuflow_ensemble import logger
import traceback

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)


def _header_length(input_csv: str):
    """Function to get header length"""

    with open(input_csv, "r") as file:
        reader = csv.reader(file)
        head = next(reader)
        return len(head)


def _header_col(input_csv: str):
    """Function to grab the row number of the header columns in the csv file"""
    with open(input_csv, "r") as file:
        reader = csv.reader(file)

        rows = [row for row in reader]
        header_row = [i for i, row in enumerate(rows) if "Flow" in row]

        return header_row[0]


def get_po_csvs(input_dir: str) -> list:
    """
    This function detects TUFLOW PO csv outputs and saves their filepaths in a list.

    Args:
        input_dir (str): Path to folder containing PO output CSVs.

    Returns:
        list: List of absolute filepaths (str) of all detected CSVs

    """
    csv_filepaths = []

    for file in os.listdir(input_dir):
        if "_po.csv" in file.lower():
            csv_filepaths.append(os.path.join(input_dir, file))
    return csv_filepaths


def _create_local_folder(dir_name: str):
    """
    This function creates a working folder in local directory to copy CSV files.
    """

    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)

    os.mkdir(dir_name)


def copy_po_csvs(csv_filepaths: list[str]) -> list[str]:
    """
    This function copies PO results files to local folder.
    Args:
        csv_filepaths: A list of CSV files to copy.

    Returns:
        A list of filepaths of copied CSVs, skipping empty files that were copied.
    """

    local_fol = "_local"
    _create_local_folder(local_fol)

    filepaths = []

    for path in csv_filepaths:
        target = os.path.join(local_fol, os.path.basename(path))
        filepaths.append(target)
        shutil.copy(path, target)

    # Filter out empty dataframes. This has to be done after copy due to file permissions.

    new_filepaths = []

    for path in filepaths:
        try:
            head_len = _header_length(path)
            df = pd.read_csv(path, usecols=range(0, head_len - 1), header=None)
            new_filepaths.append(path)
        except pd.errors.EmptyDataError:
            print(f"Empty CSV file {os.path.basename(path)}")

    return new_filepaths


def parse_po_csv(input_file: str) -> pd.DataFrame or None:
    """
    This function converts PO_line CSVs to pandas dataframes. Does nothing if csv is empty.

    Args:
        input_file: Path to PO file CSV.

    Returns:
        Pandas DataFrame with cleaned data from csv. The name of the DataFrame follows the name of the csv file.
    """
    try:
        # Get length of header to drop dummy columns
        head_len = _header_length(input_file)
        df = pd.read_csv(input_file, usecols=range(0, head_len), header=None)

        # Set header - first col with "Flow" string
        head_col = _header_col(input_file)
        df.columns = df.iloc[head_col]
        df = df.drop(index=head_col)
    except pd.errors.EmptyDataError:
        exit()

    # Drop first column with the filename
    first_column = df.columns[0]
    df.drop(first_column, axis=1, inplace=True)

    # Set index as time increment
    df.set_index(df.columns[0], inplace=True)

    # Label columns with numbers to avoid duplicates
    df.columns = [f"{column}.{i}" for i, column in enumerate(df.columns)]
    # Run ID read by input filename prepared by TUFLOW.
    df.name = os.path.basename(input_file)
    return df


def _parse_run_id(run_id: str) -> tuple[str, str, str]:
    """
    This function reads the .csv filename and parses it into storm event, duration and temporal pattern respectively.

    Args:
        run_id: Name of csv file.

    Returns:
        a 3x1 tuple of strings with storm, duration and temporal pattern.

    """

    run_id_l = run_id.lower()

    storm = (
        re.search(r"_.*?_", run_id_l).group().replace("_", "")
    )  # Will match the string between the first two underscores.
    duration = re.search(r"\d{1,4}m", run_id_l).group()
    temp_patt = re.search(r"tp\d*", run_id_l).group()

    return storm, duration, temp_patt


def _get_po_lines(po_df: pd.DataFrame) -> list[str]:
    """
    Grabs names of columns containing max flow, i.e. the po lines. Reads dataframes files generated by parse_po_csv()

    Args:
        po_df:

    Returns:
        A list of column names containing the PO_line names
    """
    po_lines = []

    for column, values in po_df.items():
        if "Flow" in column:
            location = po_df[column][0]
            po_lines.append(location)
    return po_lines


def _get_all_max_flows(po_sr: pd.Series) -> pd.Series:
    """
    This function processes a cleaned dataframe containing PO line data and returns a pd.Series object with the
    maximum flow in each PO line for that run.

    Args:
        po_sr: Pandas DataFrame containing cleaned csv data.

    Returns:
        A pandas series containing the maximum flows for all PO lines in the run. The series .name is equal to the
        po_df name.
    """
    po_lines = _get_po_lines(po_sr)

    po_lines_columns = [f"Max Flow {s}" for s in po_lines]

    columns = ["Run ID", "Event", "Duration", "Temporal Pattern"] + po_lines_columns

    po_max_flows = []

    for column, values in po_sr.items():
        if "Flow" in column:
            # Get max flow in pd Series, ignoring text (typically PO line title)
            po_max_flows.append((pd.to_numeric(po_sr[column], errors="coerce").max()))

    run_id = po_sr.name

    run_id_values = list(_parse_run_id(run_id))
    new_row = [run_id] + run_id_values + po_max_flows

    sr = pd.Series(new_row, index=columns)
    sr.name = run_id

    return sr


def concat_po_srs(max_flows_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    This function reads a list of pd.Series containing dataframes with max flows for each run configuration. Only input
    dataframes generated by parse_po_csv().

    Args:
        max_flows_dfs: A list containing all dataframes to concatenate (should be output from get_all_max_flows).

    Returns:
        A DataFrame containing all results mimicking legacy spreadsheet.

    """

    all_runs_df = pd.DataFrame()

    for df in max_flows_dfs:
        new_row = _get_all_max_flows(df)
        all_runs_df = pd.concat([all_runs_df, new_row], axis=1)
    return all_runs_df.T


def _split_po_dfs(df: pd.DataFrame) -> list[pd.DataFrame]:
    """
    This function takes all results dataframe with multiple PO lines and splits the dataframes according to each po line
    for better manipulation.

    Args:
        df: DataFrame containing data for multiple PO lines.

    Returns:
        a list containing a DataFrame for each po_line.

    """

    po_lines = []
    po_line_dfs = []

    for column, values in df.items():
        if "Max Flow" in column:
            po_lines.append(column)

    for po_line in po_lines:
        split_df = df
        excluded_columns = [x for x in po_lines if x != po_line]
        po_line_dfs.append(split_df.drop(columns=excluded_columns))

    return po_line_dfs


def _split_event(df: pd.DataFrame) -> list[pd.DataFrame]:
    """
    This function takes a dataframe with multiple events and splits the dataframes according to each event for better
    manipulation.

    Args:
        df: DataFrame containing data for multiple events

    Returns:
        a list containing a DataFrame for each po_line
    """

    unique_events = df["Event"].unique().tolist()

    event_dfs = []

    for event in unique_events:
        event_dfs.append(df[df["Event"] == event])

    return event_dfs


def _drop_sort_duration(df: pd.DataFrame) -> pd.DataFrame:
    """
    This function drops all non-numeric chars from the index ('Duration') column in dataframe and sorts the dataframe by
    numeric value.

    Args:
        df: DataFrame with 'Duration' column.

    Returns:
        a DataFrame sorted by duration (numeric value only).

    """
    sorted_df = df
    # Remove alphabetical chars from minutes
    sorted_df.index = sorted_df.index.map(lambda x: (re.sub(r"[a-zA-Z]", "", str(x))))
    sorted_df.index = sorted_df.index.map(lambda x: int(x))
    sorted_df = sorted_df.sort_index()
    return sorted_df


def _get_col_name(value, input_row):
    """Get column name of value in row generated by df.apply() method."""
    col_name = input_row[input_row == value].index[0]
    return col_name


def _get_crit_tp(row: pd.Series) -> str:
    """
    This function is to be applied to processed dataframe of storm durations vs temporal patterns. Used
    to create a new column with critical storms for each duration. Do not use by itself, used via dataframe apply()
    method!

    Args:
        row: A pd.Series passed through via df.apply().

    Returns:
        a string containing name of column with critical storm.
    """
    median = row["Median"]

    diffs = {}

    # Skip nan values that occur because of missing results for a particular temporal pattern / duration csv.
    row = row.dropna()

    for cell in row:
        col_name = _get_col_name(cell, row)
        if "tp" in col_name:
            diffs[col_name] = cell - median

    positive_diffs = {k: v for k, v in diffs.items() if v > 0}

    try:
        crit_tp = min(positive_diffs, key=positive_diffs.get)
    except ValueError:
        # Handle cases where there's no storm above the median value (i.e.all temporal pattern flows == Median).
        # In this case the function will grab the first storm that matches the median value. In the future a warning
        # should be raised.
        crit_tp = "NA"

    return crit_tp


def _tp_vs_max_flow_df(df: pd.DataFrame) -> tuple:
    """
    This function takes a df filtered by one event and one po_line and generates a dataframe presenting storm duration
    (x) vs temporal patterns (y), as well as average, median and critical temporal patterns for the run. Event and
    PO_line are stored in the DataFrame name.

    Note that po_line name will be lost in this process!

    Args:
        df: DataFrame with data for one event and po_line

    Returns:
        A DataFrame sorted by duration (x) vs temporal pattern (y), avg/median values, and critical storm.
    """
    event = df["Event"].unique().tolist()[0]

    po_line: str = ""

    for column, values in df.items():
        if "Max Flow" in column:
            po_line = str(column)

    dur_tp_df = df.pivot(index="Duration", columns="Temporal Pattern", values=po_line)
    dur_tp_df = _drop_sort_duration(dur_tp_df)

    tp_cols = [col for col in dur_tp_df.columns if "tp" in col]

    dur_tp_df["Average"] = dur_tp_df[tp_cols].mean(axis=1)
    dur_tp_df["Median"] = dur_tp_df[tp_cols].median(axis=1)
    dur_tp_df["Critical TP"] = dur_tp_df.apply(_get_crit_tp, axis=1)

    dur_tp_df.name = f"{po_line}: {event} Event"

    return event, po_line, dur_tp_df


def all_critical_storms(all_runs_df: pd.DataFrame) -> list[pd.DataFrame]:
    """
    This function outputs one dataframe for each event and PO line, representing all the temporal patterns and
    durations, as well as the critical storms for each duration.


    Args:
        all_runs_df: Pandas DataFrame with maximum flows provided against temporal pattern and duration.

    Returns:
        A list of dataframes each with max flow data + average, median and critical storms.

    """
    df = all_runs_df

    events = all_runs_df["Event"].unique()
    durations = all_runs_df["Duration"].unique()
    temp_patts = all_runs_df["Temporal Pattern"].unique()

    po_lines_dfs = _split_po_dfs(all_runs_df)

    working_dfs = []

    for _ in po_lines_dfs:
        final_dfs = _split_event(_)
        working_dfs.append(final_dfs)

    all_crit_tp_dfs = []
    for x in working_dfs:
        for y in x:
            event, po_line, df = _tp_vs_max_flow_df(y)
            sorted_df = _drop_sort_duration(df)
            sorted_df.name = f"{event}: {po_line}"
            all_crit_tp_dfs.append(sorted_df)

    return all_crit_tp_dfs


def summarize_results(crit_tp_df: pd.DataFrame):
    """
    This function reads a dataframe listing all critical storms and finds the duration / tp combination with highest
    critical storm.

    Args:
        crit_tp_df: Pandas DataFrame with critical storms and meta-statistics.

    Returns:
        Pandas Series summarizing critical storm configuration for a po_line.

    """
    max_med = crit_tp_df["Median"].max()
    crit_duration = crit_tp_df["Median"].idxmax()

    crit_tp = crit_tp_df.loc[crit_duration, "Critical TP"]

    event, po_line = str(crit_tp_df.name).split(":", 1)
    po_line = po_line.replace("Max Flow ", "")

    if crit_tp == "NA":
        crit_max_flow = "NA"
    else:
        crit_max_flow = crit_tp_df.loc[crit_duration, crit_tp]

    index = ["Event", "PO Line", "Critical Duration", "Critical TP", "Critical TP Flow"]
    values = [event, po_line, crit_duration, crit_tp, crit_max_flow]

    return pd.Series(data=values, index=index)


def _str_to_valid_filename(name: str) -> str:
    """
    Removes troublesome chars from filename. Tries not over-prescribe - keeps underscore and dash chars as this is
    common in TUFLOW results files.

    Args:
        name: Proposed filename for cleaning.

    Returns:
        a string with more valid filename.
    """

    invalid_chars = r"%:/,\[]<>*?"
    valid_name = ""

    for c in name:
        if c in invalid_chars:
            c = "-"
        valid_name += c

    return valid_name


def plot_results(
    crit_storm_df: pd.DataFrame, output_path: str, strip_plot=True
) -> None:
    """
    Plotting function for critical storms dataframe. Plots to PNG file with filename in format 'storm event- po_line'.
    No return value.

    Args:
        crit_storm_df: tp vs duration results to plot.
        output_path: Folder to generate all results.
        strip_plot: Whether to show individual temporal patterns as points overlaid on each box. Defaults to True.
    Returns:
        No return value, outputs plots as files directly into output_path.

    """

    # Only plot tp columns, ignoring meta-stats column (e.g. Median).

    fig, ax = plt.subplots()

    name = crit_storm_df.name

    tp_cols = [col for col in crit_storm_df.columns if "tp" in col]

    for col in tp_cols:
        crit_storm_df[col] = crit_storm_df[col].astype(float)

    data = crit_storm_df[tp_cols].T
    ax = sns.boxplot(data, color="lightyellow", saturation=1.0)

    if strip_plot:
        ax = sns.stripplot(data, palette="dark:black", jitter=0, size=3)

    ax.set_xlabel("Duration (m)")
    ax.set_ylabel("Max Flow (cu.m/sec)")
    ax.set_title(name)

    filename = _str_to_valid_filename(name)
    filepath = os.path.join(output_path, filename)

    # Save as png in local directory
    plt.savefig(filepath + ".png", dpi=200)

    plt.close()


def _skipped_inputs(raw_inputs: list, saved_inputs: list) -> list:
    raw = [os.path.basename(i) for i in raw_inputs]
    saved = [os.path.basename(i) for i in saved_inputs]

    skipped = []

    for r in raw:
        if r not in saved:
            skipped.append(r)

    return skipped


def main(input_path: str, output_path: str):
    # Create Log Object

    log_file = logger.Logger()
    results_file = logger.Logger()

    try:
        # Read input folder and download/copy files
        raw_inputs = get_po_csvs(input_path)
        saved_inputs = copy_po_csvs(raw_inputs)

        # Log events
        log_file.log(f"Inputs copied to local folder from source folder {input_path}:")
        log_file.log([os.path.basename(saved_input) for saved_input in saved_inputs])
        log_file.log("\nSkipped inputs:")
        log_file.log(_skipped_inputs(raw_inputs, saved_inputs))

        # Get max flows
        all_max_flows = []

        for csv in saved_inputs:
            df1 = parse_po_csv(csv)
            all_max_flows.append(df1)

        df1 = concat_po_srs(all_max_flows)

        # Log resulting maximum flows for all PO Lines

        log_file.log(df1)

        # Generate Dataframe with max flows / critical storm per PO Line
        all_crit = all_critical_storms(df1)

        # Log critical storms
        log_file.log(all_crit)

        # Plot
        for df in all_crit:
            plot_results(df, output_path)

        # Generate Results
        results_sr = []

        for df in all_crit:
            results_sr.append(summarize_results(df))

        # Log results
        results_file.log(" \n\n\n###### RESULTS ###### \n\n\n")

        results_df = pd.DataFrame(results_sr)

        results_file.log(results_sr)

        # Results to file
        results_file.write_to_txt(output_path, "results.txt")
        status = "Success"

    except Exception:
        print("tuflow_ensemble has encountered an error! Please see log.txt.")
        # Capture standard error to log.txt.
        err = (
            f"Error encountered! Please report this through the issues tab in https://github.com/hydroEng/tuflow_ensemble."
            f"\n\nTraceback Message:\n\n{traceback.format_exc()}"
        )
        log_file.log(str(err))
        status = "Error"

    # Export log to file
    log_file.write_to_txt(output_path, "log.txt")
    return status


if __name__ == "__main__":
    input_dir = r""
    output_dir = r""
    main(input_dir, output_dir)
