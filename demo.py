"""One-command synthetic evaluation: python demo.py."""
import argparse
import json
from pathlib import Path
from anpr.platform import Platform
from anpr.simulator import run
from anpr.alerts import list_alerts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vehicles', type=int, default=320)
    parser.add_argument('--seed', type=int, default=26127)
    parser.add_argument('--output', default='output/evaluation.json')
    args = parser.parse_args()
    if not 1 <= args.vehicles <= 1000:
        parser.error('--vehicles must be 1–1000')
    platform = Platform()
    report = run(platform, args.vehicles, args.seed)
    print('\nNEXUS / SIH26127 — SYNTHETIC NOISE BENCHMARK (not real-world accuracy)\n')
    print(f'{"Condition":12} {"Passes":>7} {"Single*":>10} {"Voting":>10} {"Online ID":>10} {"Final ID":>10}')
    for row in report['accuracy']:
        print(f'{row["condition"]:12} {row["passes"]:7} {row["single"]:9.2f}% {row["voted"]:9.2f}% {row["online"]:9.2f}% {row["resolved"]:9.2f}%')
    print('\n* Single includes positional normalization. Final ID includes later canonical upgrades.')
    report['trajectory'] = platform.search('DL01AB1234', 'admin')
    report['analytics'] = platform.analytics()
    report['alerts'] = list_alerts(platform.db)
    for title, value in [('Trajectory', report['trajectory']), ('Analytics', report['analytics']['summary']), ('Alerts', report['alerts'])]:
        print('\n' + title + '\n' + json.dumps(value, indent=2))
    print('\nIntegrity:', report['integrity']['valid'])
    # Isolated in-memory database: tamper test never changes the dashboard DB.
    with platform.db.transaction():
        platform.db.conn.execute('UPDATE detections SET confidence=0 WHERE id=(SELECT MIN(id) FROM detections)')
    report['tamper_detected'] = not platform.db.verify()['valid']
    print('Tampering detected:', report['tamper_detected'])
    assert report['integrity']['valid'] and report['tamper_detected']
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Full evaluation:', target.resolve())
    platform.db.close()


if __name__ == '__main__':
    main()
