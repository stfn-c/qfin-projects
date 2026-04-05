import platform
import sys
import os
import argparse
import numpy as np
import time
from multiprocessing import Pool, cpu_count

original_sys_path = sys.path.copy()

current_dir = os.path.dirname(os.path.abspath(__file__))
os_name = platform.system()

if os_name == "Linux":
    sys.path.insert(0, os.path.join(current_dir, "bin/linux_version"))
    from bin.linux_version.game_setup import run_game
elif os_name == "Windows":
    sys.path.insert(0, os.path.join(current_dir, "bin/windows_version"))
    from bin.windows_version.game_setup import run_game
elif os_name == "Darwin":
    sys.path.insert(0, os.path.join(current_dir, "bin/mac_version"))
    from bin.mac_version.game_setup import run_game
else:
    raise ValueError("Unsupported OS")

from base import Product

print("Imports Completed")

sys.path = original_sys_path

# ======================Do Not Change Anything above here====================

from nifty_trader_manager import PlayerAlgorithm


def run_single_simulation(args_tuple):
    """Function to run a single simulation"""
    run_number, products, num_timestamps, save_data, instance_num, state_logging, bot_version = (
        args_tuple
    )

    # Set bot version in subprocess
    if bot_version is not None:
        import nifty_trader_manager
        nifty_trader_manager.BOT_VERSION = bot_version

    # Add a small delay before starting to avoid CSV conflicts (only if saving)
    if save_data:
        time.sleep(0.5)

    player_bot = PlayerAlgorithm(
        products, instance_num=instance_num, num_timestamps=num_timestamps
    )

    # Disable data saving if requested
    if not save_data and hasattr(player_bot._bot, "set_save_data"):
        player_bot._bot.set_save_data(False)

    # Enable state logging if requested
    if state_logging and hasattr(player_bot._bot, "set_state_logging"):
        player_bot._bot.set_state_logging(True)

    pnl = run_game(player_bot, num_timestamps, products)

    # Save data for this run (only if enabled)
    if save_data and hasattr(player_bot._bot, "save_data"):
        player_bot._bot.save_data()

    # Save state log if enabled
    if state_logging and hasattr(player_bot._bot, "save_state_log"):
        player_bot._bot.save_state_log()

    print(f"Run {run_number:2d}: PnL = {pnl:,.2f}")
    return pnl


def interactive_menu():
    """Interactive CLI menu for configuration"""
    print("\n" + "=" * 60)
    print(" " * 20 + "NIFTY TRADER v1.0")
    print("=" * 60)

    print("\nSIMULATION CONFIGURATION\n")

    # Bot version selection
    print("1. Select bot version:")
    print("   [1] Version 1 - Simple Market Maker")
    print("   [2] Version 2 - Enhanced Position Management") 
    print("   [4] Version 4 - Clean Market Maker (3.8 spread)")
    print("   [5] Version 5 - Dynamic Level Market Maker")
    print("   [6] Version 6 - Volatility-Adaptive Market Maker")
    print("   [7] Version 7 - Advanced Market Maker with Whale Detection")
    print("   [9] Version 9 - v7 + Position-Based Skewing")
    print("   [10] Version 10 - Data Logger (Observer Only)")
    print("   [11] Version 11 - Pure ML Trading Bot")
    print("   [12] Version 12 - Decision Tree + Whale Detection")
    print("   [13] Version 13 - Hybrid Market Maker + Decision Tree")
    version_choice = input("\n   Select version (1,2,4-7,9-13) [13]: ").strip() or "13"
    
    # Map version choices to actual versions
    version_map = {"1": 1, "2": 2, "4": 4, "5": 5, "6": 6, "7": 7, "9": 9, "10": 10, "11": 11, "12": 12, "13": 13}
    if version_choice in version_map:
        selected_version = version_map[version_choice]
    else:
        print(f"Invalid version choice '{version_choice}', using version 13")
        selected_version = 13

    # Number of runs
    print("\n2. Number of simulations to run:")
    print("   [1] Single run")
    print("   [2] 5 runs")
    print("   [3] 11 runs (default)")
    print("   [4] 20 runs")
    print("   [5] 33 runs (fast template)")
    print("   [6] Custom")
    runs_choice = input("\n   Select (1-6) [3]: ").strip() or "3"

    if runs_choice == "1":
        runs = 1
        single = True
    elif runs_choice == "2":
        runs = 5
        single = False
    elif runs_choice == "3":
        runs = 11
        single = False
    elif runs_choice == "4":
        runs = 20
        single = False
    elif runs_choice == "5":
        runs = 33
        single = False
    else:
        runs = int(input("   Enter custom number of runs: "))
        single = runs == 1

    # Always use parallel for multiple runs
    if not single:
        parallel = True
        print("\n3. Execution mode: Parallel (automatically enabled for multiple runs)")
    else:
        parallel = False

    # Timestamps
    print("\n4. Timestamps per simulation:")
    print("   [1] 1,000 (quick test)")
    print("   [2] 5,000 (fast)")
    print("   [3] 10,000 (medium)")
    print("   [4] 20,000 (full - default)")
    print("   [5] Custom")
    time_choice = input("\n   Select (1-5) [4]: ").strip() or "4"

    if time_choice == "1":
        timestamps = 1000
    elif time_choice == "2":
        timestamps = 5000
    elif time_choice == "3":
        timestamps = 10000
    elif time_choice == "4":
        timestamps = 20000
    else:
        timestamps = int(input("   Enter custom timestamps: "))

    # CSV saving is always enabled
    no_save = False
    print("\n5. CSV data will be saved automatically.")
    
    # State logging (JSON) option
    print("\n6. Save detailed state logging (JSON)?")
    print("   [1] Yes (default - includes order book snapshots)")
    print("   [2] No (CSV only)")
    state_choice = input("\n   Select (1-2) [1]: ").strip() or "1"
    state_logging = state_choice == "1"

    # Summary
    print("\n" + "=" * 60)
    print("CONFIGURATION SUMMARY")
    print("-" * 60)
    print(f"   Bot Version: {selected_version}")
    print(f"   Runs:        {runs}")
    print(f"   Mode:        {'Parallel' if parallel else 'Sequential'}")
    print(f"   Timestamps:  {timestamps:,}")
    print(f"   Save CSV:    Yes (always)")
    print(f"   Save JSON:   {'Yes' if state_logging else 'No'}")
    print(
        f"   Est. Time:   ~{(runs * timestamps * 0.002 / (11 if parallel else 1)):.0f} seconds"
    )
    print("=" * 60)

    confirm = input("\nStart simulation? (y/n) [y]: ").strip().lower() or "y"

    if confirm != "y":
        print("Simulation cancelled.")
        exit(0)

    print("\nStarting simulation...\n")

    return single, runs, timestamps, parallel, no_save, state_logging, selected_version


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run trading simulation")
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive configuration mode",
    )
    parser.add_argument(
        "-t",
        "--template",
        choices=[
            "mini",
            "debug",
            "quick",
            "test",
            "standard",
            "competition",
            "statistical",
            "exhaustive",
            "5k",
            "10k",
            "20k",
        ],
        help="Use preset templates (use --templates to list all)",
    )
    parser.add_argument(
        "--templates",
        action="store_true",
        help="List all available templates with descriptions",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Run single simulation instead of multiple",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=11,
        help="Number of simulations to run (default: 11)",
    )
    parser.add_argument(
        "--timestamps",
        type=int,
        default=20000,
        help="Number of timestamps per simulation (default: 20000)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run simulations sequentially (default is parallel)",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Disable CSV saving for faster execution"
    )
    parser.add_argument(
        "--state-log",
        action="store_true",
        help="Enable state logging (automatically enabled for debug/quick templates)",
    )
    args = parser.parse_args()

    # Handle --templates flag
    if args.templates:
        print("\n" + "=" * 70)
        print(" " * 25 + "AVAILABLE TEMPLATES")
        print("=" * 70)
        print("\nDEVELOPMENT TEMPLATES:")
        print("  debug       - 1 run, 10 ticks     (Testing individual bot behavior)")
        print("  quick       - 1 run, 100 ticks    (Quick validation with state log)")
        print("  test        - 1 run, 1000 ticks   (Testing strategy changes)")
        print("\nEVALUATION TEMPLATES:")
        print("  standard    - 11 runs, 5k ticks   (Standard statistical evaluation)")
        print("  competition - 11 runs, 20k ticks  (Competition settings)")
        print("\nADVANCED TEMPLATES:")
        print("  statistical - 33 runs, 5k ticks   (High confidence statistics)")
        print("  exhaustive  - 33 runs, 20k ticks  (Complete evaluation)")
        print("\nQUICK RUNS:")
        print("  5k          - 1 run, 5k ticks     (Single run with state logging)")
        print("  10k         - 1 run, 10k ticks    (Single run with state logging)")
        print("  20k         - 1 run, 20k ticks    (Single run, NO state logging)")
        print("\nTemplate Features:")
        print("  • All templates run in parallel (use --sequential to override)")
        print("  • Debug/quick templates include state logging")
        print("  • All templates save CSV data (use --no-save to override)")
        print("=" * 70 + "\n")
        sys.exit(0)

    # Clean up any existing round marker at the start
    from pathlib import Path
    import nifty_trader_manager

    marker_file = Path(f"research/raw_data/v{nifty_trader_manager.BOT_VERSION}/.current_round")
    if marker_file.exists():
        marker_file.unlink()

    # Apply template if specified
    state_logging = getattr(args, "state_log", False)  # Use command line flag

    # Template definitions with clearer names
    templates = {
        "mini": {
            "runs": 1,
            "timestamps": 3,
            "single": True,
            "state_log": False,
            "desc": "Minimal: 1 run, 3 ticks (absolute minimum for testing)",
        },
        "debug": {
            "runs": 1,
            "timestamps": 10,
            "single": True,
            "state_log": True,
            "desc": "Debug mode: 1 run, 10 ticks with state logging",
        },
        "quick": {
            "runs": 1,
            "timestamps": 100,
            "single": True,
            "state_log": True,
            "desc": "Quick test: 1 run, 100 ticks with state logging",
        },
        "test": {
            "runs": 1,
            "timestamps": 1000,
            "single": True,
            "state_log": True,
            "desc": "Test run: 1 run, 1000 ticks",
        },
        "standard": {
            "runs": 11,
            "timestamps": 5000,
            "single": False,
            "state_log": True,
            "desc": "Standard evaluation: 11 runs, 5000 ticks",
        },
        "competition": {
            "runs": 11,
            "timestamps": 20000,
            "single": False,
            "state_log": False,
            "desc": "Competition settings: 11 runs, 20000 ticks",
        },
        "statistical": {
            "runs": 33,
            "timestamps": 5000,
            "single": False,
            "state_log": True,
            "desc": "Statistical analysis: 33 runs, 5000 ticks",
        },
        "exhaustive": {
            "runs": 33,
            "timestamps": 20000,
            "single": False,
            "state_log": False,
            "desc": "Exhaustive evaluation: 33 runs, 20000 ticks",
        },
        "5k": {
            "runs": 1,
            "timestamps": 5000,
            "single": True,
            "state_log": True,
            "desc": "Single 5k run with state logging",
        },
        "10k": {
            "runs": 1,
            "timestamps": 10000,
            "single": True,
            "state_log": True,
            "desc": "Single 10k run with state logging",
        },
        "20k": {
            "runs": 1,
            "timestamps": 20000,
            "single": True,
            "state_log": False,
            "desc": "Single 20k run (no state logging)",
        },
    }

    if args.template:
        template = templates[args.template]
        
        # Normal template handling
        args.runs = template["runs"]
        args.timestamps = template["timestamps"]
        args.single = template["single"]
        if not args.state_log:  # Only override if not explicitly set
            state_logging = template["state_log"]
        print(f"Using template '{args.template}': {template['desc']}")

    # Check for interactive mode
    if args.interactive:
        args.single, args.runs, args.timestamps, args.parallel, args.no_save, state_logging_interactive, selected_version = (
            interactive_menu()
        )
        # Override state_logging if set in interactive mode
        state_logging = state_logging_interactive
        
        # Update bot version in nifty_trader_manager
        import nifty_trader_manager
        nifty_trader_manager.BOT_VERSION = selected_version
        print(f"Bot version set to: {selected_version}")
        
        # Clean up round marker for the new version
        marker_file = Path(f"research/raw_data/v{selected_version}/.current_round")
        if marker_file.exists():
            marker_file.unlink()

    uec = Product("UEC", mpv=0.1, pos_limit=200, fine=20)
    products = [uec]
    num_timestamps = args.timestamps

    if args.single:
        # Run single simulation
        player_bot = PlayerAlgorithm(
            products, instance_num=1, num_timestamps=num_timestamps
        )

        # Enable state logging if requested
        if state_logging and hasattr(player_bot._bot, "set_state_logging"):
            player_bot._bot.set_state_logging(True)

        your_pnl = run_game(player_bot, num_timestamps, products)

        # Explicitly save data after game completes
        if hasattr(player_bot._bot, "save_data"):
            player_bot._bot.save_data()

        # Save state log if enabled
        if state_logging and hasattr(player_bot._bot, "save_state_log"):
            player_bot._bot.save_state_log()

        print(f"PnL: {your_pnl}")

        # Clean up the round marker file at the end
        if marker_file.exists():
            marker_file.unlink()
    else:
        # Run multiple simulations
        num_runs = args.runs

        print(
            f"Running {num_runs} simulations with {num_timestamps} timestamps each..."
        )

        # Default to parallel unless explicitly disabled
        use_parallel = not args.sequential

        if use_parallel:
            print(
                f"Using parallel processing with {cpu_count()} cores (use --sequential to run sequentially)"
            )
        print("-" * 50)

        save_data = not args.no_save
        
        # Get current bot version for subprocess
        current_bot_version = nifty_trader_manager.BOT_VERSION

        if use_parallel:
            # Run simulations in parallel
            # Create argument tuples for each simulation
            args_list = [
                (i + 1, products, num_timestamps, save_data, i + 1, state_logging, current_bot_version)
                for i in range(num_runs)
            ]
            with Pool() as pool:
                pnls = pool.map(run_single_simulation, args_list)
        else:
            # Run simulations sequentially
            pnls = []
            for i in range(num_runs):
                pnl = run_single_simulation(
                    (i + 1, products, num_timestamps, save_data, i + 1, state_logging, current_bot_version)
                )
                pnls.append(pnl)

        print("-" * 50)

        # Show current bot version/stage
        from nifty_trader_manager import BOT_VERSION

        print(f"\nBOT VERSION: Stage {BOT_VERSION}")

        # Show individual instance PnLs
        print(f"\nINDIVIDUAL RESULTS:")
        for i, pnl in enumerate(pnls, 1):
            print(f"  Instance {i:2d} PnL: {pnl:,.2f}")

        # Count profitable vs losing instances
        profitable = sum(1 for pnl in pnls if pnl > 0)
        losing = sum(1 for pnl in pnls if pnl < 0)
        breakeven = sum(1 for pnl in pnls if pnl == 0)

        print(f"\nWIN/LOSS SUMMARY:")
        print(f"  Profitable: {profitable}/{num_runs} ({profitable/num_runs*100:.1f}%)")
        print(f"  Losing:     {losing}/{num_runs} ({losing/num_runs*100:.1f}%)")
        if breakeven > 0:
            print(
                f"  Breakeven:  {breakeven}/{num_runs} ({breakeven/num_runs*100:.1f}%)"
            )

        print("-" * 50)

        # Calculate normalized PnL for different tick counts
        pnls_per_actual = [pnl / num_timestamps for pnl in pnls]  # Per tick
        pnls_per_5k = [pnl * (5000 / num_timestamps) for pnl in pnls]
        pnls_per_20k = [pnl * (20000 / num_timestamps) for pnl in pnls]

        print(f"\nKEY METRICS (Normalized):")
        print(f"  Actual run length:             {num_timestamps:,} ticks")
        print(f"  Average PnL per tick:          {np.mean(pnls_per_actual):,.2f}")
        print(f"  Average PnL per 5,000 ticks:  {np.mean(pnls_per_5k):,.2f}")
        print(f"  Average PnL per 20,000 ticks: {np.mean(pnls_per_20k):,.2f}")

        print(f"\nFULL STATISTICS (all {num_runs} runs):")
        print(f"  Average PnL: {np.mean(pnls):,.2f}")
        print(f"  Std Dev:     {np.std(pnls):,.2f}")
        print(f"  Min PnL:     {np.min(pnls):,.2f}")
        print(f"  Max PnL:     {np.max(pnls):,.2f}")
        print(
            f"  Sharpe:      {np.mean(pnls)/np.std(pnls) if np.std(pnls) > 0 else 0:.2f}"
        )

        # Calculate trimmed statistics if we have enough runs
        if num_runs > 4:
            sorted_pnls = sorted(pnls)
            trimmed_pnls = sorted_pnls[2:-2]  # Remove bottom 2 and top 2

            print(f"\nTRIMMED STATISTICS (excluding 2 best & 2 worst):")
            print(f"  Average PnL: {np.mean(trimmed_pnls):,.2f}")
            print(f"  Std Dev:     {np.std(trimmed_pnls):,.2f}")
            print(f"  Min PnL:     {np.min(trimmed_pnls):,.2f}")
            print(f"  Max PnL:     {np.max(trimmed_pnls):,.2f}")
            print(
                f"  Sharpe:      {np.mean(trimmed_pnls)/np.std(trimmed_pnls) if np.std(trimmed_pnls) > 0 else 0:.2f}"
            )

            print(f"\nOUTLIERS REMOVED:")
            print(f"  Bottom 2: {sorted_pnls[0]:,.2f}, {sorted_pnls[1]:,.2f}")
            print(f"  Top 2:    {sorted_pnls[-2]:,.2f}, {sorted_pnls[-1]:,.2f}")

            diff = np.mean(pnls) - np.mean(trimmed_pnls)
            print(
                f"\n  Difference: {abs(diff):,.2f} (trimmed is {'lower' if diff > 0 else 'higher'})"
            )

    # Clean up the round marker file at the end
    if marker_file.exists():
        marker_file.unlink()
