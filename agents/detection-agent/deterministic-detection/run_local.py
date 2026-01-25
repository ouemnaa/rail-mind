"""
Local launcher for the RailMind detection runner.

Usage:
  python run_local.py --ticks 50 --seed 42

It forwards CLI args to run_detection.main() (same folder).
"""

if __name__ == '__main__':
    from run_detection import main
    main()
