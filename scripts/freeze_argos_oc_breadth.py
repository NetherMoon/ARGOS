"""Freeze generic ARGOS-OC breadth inputs without simulator calls."""

import argparse
from pathlib import Path

from argos.oc_basic.breadth_plan import freeze_protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientific-root", type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    protocol = freeze_protocol(args.scientific_root.resolve(), source)
    print(
        f"Frozen {protocol['contexts']} contexts; {protocol['search_panel_size']}-scenario "
        f"search panels; {protocol['assessment_pairs_per_selected_method']} assessment pairs"
    )


if __name__ == "__main__":
    main()
