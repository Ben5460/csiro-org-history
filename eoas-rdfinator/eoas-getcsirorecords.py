#!/usr/bin/env python3

from EoasOaiClient import EoasOaiClient

def main():
    client = EoasOaiClient(verbose=True)
    client.download_record_and_relations("A000196")

if __name__ == "__main__":
    main()
