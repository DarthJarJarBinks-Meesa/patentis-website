"""Background worker entry."""

if __name__ == "__main__":
    print("Patentis workers:")
    print("  python -m workers.scheduler all|masking|scoring|figures|neighbors")
    print("  python -m workers.bulk_index /path/to/uspto/xml")
    print("  python models/auto_trainer.py")
