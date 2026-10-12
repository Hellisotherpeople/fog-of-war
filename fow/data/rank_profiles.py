"""National rank identities separate from the tactical 0–18 command scale.

A warrant, technical grade, rating and appointment are not interchangeable.
Profiles retain the existing national line ranks and describe branches explicitly.
See docs/RANKS.md for sources and the limits of the common command scale.
"""
from dataclasses import dataclass, replace
from functools import lru_cache

from .ranks import ladder


@dataclass(frozen=True)
class Rank:
    key: str
    title: str
    short: str
    grade: int
    branch: str = 'line'
    order: int = 0
    authority: int = -1
    since: float = 1939
    until: float = 1946
    appointment: str = ''

    @property
    def command_grade(self):
        return self.grade if self.authority < 0 else self.authority

    @property
    def category(self):
        if self.branch.startswith('warrant'):
            return 'warrant officer'
        if self.branch == 'technical':
            return 'technical enlisted'
        return self.branch if self.branch != 'line' else 'commissioned officer' if self.grade >= 8 else 'enlisted / NCO'


CW = ('uk', 'canada', 'australia', 'newzealand', 'india')


@lru_cache(maxsize=128)
def catalog(nation, service='army'):
    out = []
    seen = set()
    for grade, (title, short) in enumerate(ladder(nation, service)):
        if title in seen:
            continue  # one historical rank, not several promotions to the same title
        seen.add(title)
        out.append(Rank(f'line:{grade}', title, short, grade, order=grade * 10))

    def remove(*grades):
        out[:] = [r for r in out if r.grade not in grades or r.branch != 'line']

    def add(key, title, short, grade, branch='line', order=None, authority=-1, since=1939, until=1946, appointment=''):
        out.append(Rank(key, title, short, grade, branch, grade * 10 if order is None else order,
                        authority, since, until, appointment))

    if nation == 'usa' and service in ('army', 'air'):
        remove(6, 7)
        add('line:master', 'Master Sergeant', 'MSgt.', 7, order=70)
        add('line:first', 'First Sergeant', '1st Sgt.', 7, order=70, appointment='company senior NCO')
        for grade, name in ((2, 'Fifth'), (3, 'Fourth'), (4, 'Third')):
            add(f'technical:{grade}', f'Technician {name} Grade', f'T/{7-grade}', grade,
                'technical', authority=0, since=1942 + 7 / 365)
        add('warrant:pre1941', 'Warrant Officer', 'WO', 7, 'warrant', order=75, authority=1, until=1941 + 232 / 365)
        add('warrant:junior', 'Warrant Officer (Junior Grade)', 'WOJG', 7, 'warrant', order=80, authority=1, since=1941 + 232 / 365)
        add('warrant:chief', 'Chief Warrant Officer', 'CWO', 7, 'warrant', order=90, authority=1, since=1941 + 232 / 365)
        if service == 'air':
            add('flight:officer', 'Flight Officer', 'F/O', 7, 'flight', order=80, authority=1, since=1942 + 187 / 365)
    elif nation == 'india' and service == 'army':
        remove(4, 5, 6, 7)
        add('line:chm', 'Company Havildar Major', 'CHM', 5, appointment='company senior NCO')
        for key, title, grade, order in (('jemadar','Jemadar',6,60), ('subedar','Subedar',7,70),
                                        ('major','Subedar Major',7,75)):
            add('vco:'+key, title, title, grade, "Viceroy's commission", order=order,
                appointment='Indian unit officer')
    elif nation in CW and service == 'army':
        remove(5, 6, 7)
        add('line:colour', 'Colour Sergeant', 'CSgt.', 4, order=40, appointment='infantry company quartermaster')
        add('warrant:iii', 'Warrant Officer Class III', 'WOIII', 5, 'warrant', order=50, until=1940.5,
            appointment='platoon sergeant major')
        add('warrant:ii', 'Warrant Officer Class II', 'WOII', 6, 'warrant', order=60, appointment='company sergeant major')
        add('warrant:i', 'Warrant Officer Class I', 'WOI', 7, 'warrant', order=70, appointment='regimental sergeant major')
    elif nation in CW and service == 'air':
        remove(6, 7)
        add('line:ac1', 'Aircraftman 1st Class', 'AC1', 0, order=5)
        if nation == 'canada':
            add('warrant:ii', 'Warrant Officer Class II', 'WO2', 6, 'warrant', order=60)
            add('warrant:i', 'Warrant Officer Class I', 'WO1', 7, 'warrant', order=70)
        else:
            add('warrant:raf', 'Warrant Officer', 'W/O', 7, 'warrant', order=70)
    elif nation in ('usa', *CW) and service == 'navy':
        remove(7)
        # Wartime naval warrants were specialty titles, not the modern W-1–W-5 ladder.
        specialties = [('boatswain', 'Boatswain', 'Bsn.'), ('gunner', 'Gunner', 'Gnr.'),
                       ('machinist', 'Machinist', 'Mach.'), ('carpenter', 'Carpenter', 'Carp.'),
                       ('pharmacist', 'Pharmacist', 'Pharm.'), ('electrician', 'Electrician', 'Elec.'),
                       ('radio', 'Radio Electrician', 'R.Elec.'), ('pay', 'Pay Clerk', 'P.Clk.'),
                       ('torpedo', 'Torpedoman', 'Torp.'), ('clerk', "Ship's Clerk", 'S.Clk.'),
                       ('photo', 'Photographer', 'Photo.'), ('weather', 'Aerographer', 'Aero.')] if nation == 'usa' else [
                       ('boatswain', 'Boatswain', 'Bsn.'), ('gunner', 'Gunner', 'Gnr.'),
                       ('torpedo','Torpedo Gunner','T.Gnr.'), ('signal','Signal Boatswain','S.Bsn.'),
                       ('engineer', 'Engineer', 'Eng.'), ('shipwright', 'Shipwright', 'Ship.'),
                       ('electrician','Electrician','Elec.'), ('radio','Telegraphist','Tel.'),
                       ('ordnance','Ordnance Officer','Ord.'), ('writer','Writer Officer','Wr.'),
                       ('supply','Supply Officer','Sup.'), ('cook','Cook','Cook')]
        for key, title, short in specialties:
            since = 1942.57 if nation == 'usa' and key in ('torpedo','clerk','photo','weather') else 1939
            add('warrant:' + key, title if nation == 'usa' else 'Warrant '+title, short,
                7, 'warrant:' + key, order=70, authority=1, since=since)
            add('warrant:chief:' + key, ('Chief ' if nation == 'usa' else 'Commissioned ') + title,
                ('Ch.' if nation == 'usa' else 'C.') + short, 7, 'warrant:' + key, order=80, authority=1, since=since)
    elif nation == 'germany' and service in ('army', 'air'):
        remove(0, 1, 2)
        add('line:private', 'Flieger' if service == 'air' else 'Schütze', 'Flg.' if service == 'air' else 'Schtz.', 0, order=0)
        add('line:senior_private', 'Oberflieger' if service == 'air' else 'Oberschütze', 'OFl.' if service == 'air' else 'OSchtz.', 1, order=10)
        add('line:gefreiter', 'Gefreiter', 'Gefr.', 2, order=20, authority=1)
        add('line:obergefreiter', 'Obergefreiter', 'OGefr.', 2, order=22, authority=1)
        add('line:stabsgefreiter', 'Stabsgefreiter', 'StGefr.', 2, order=24, authority=1)
        if service == 'air':
            remove(18)
            add('line:18', 'Generalfeldmarschall', 'GFM', 18)
            add('special:reichsmarschall', 'Reichsmarschall', 'RM', 18, 'special appointment', order=190, since=1940.55)
    elif nation == 'japan' and service in ('army', 'air'):
        remove(0, 1, 2, 3, 4, 5, 6, 7)
        for key, title, short, grade, order in (
            ('private2', 'Nitōhei', 'Pvt.2', 0, 0), ('private1', 'Ittōhei', 'Pvt.1', 1, 10),
            ('superior', 'Jōtōhei', 'Sup.Pvt.', 1, 15), ('lance', 'Heichō', 'L/Cpl.', 2, 20),
            ('corporal', 'Gochō', 'Cpl.', 3, 30), ('sergeant', 'Gunsō', 'Sgt.', 4, 40),
            ('major', 'Sōchō', 'Sgt.Maj.', 6, 60)):
            add('line:' + key, title, short, grade, order=order)
        add('warrant:juni', "Jun'i", 'WO', 7, 'warrant', order=70, authority=1)
    elif nation == 'ussr' and service in ('army', 'air'):
        # Starshina is a senior NCO; there was no wartime praporshchik ladder.
        add('line:senior_lieutenant', 'Starshiy Leytenant', 'St.Lt.', 9, order=95)
    elif nation == 'france' and service in ('army', 'air'):
        add('line:aspirant', 'Aspirant', 'Asp.', 7, 'officer candidate', order=75, authority=1)
    elif nation == 'poland' and service in ('army', 'air'):
        # The existing chorąży titles are warrant grades, not extra sergeant stripes.
        remove(7)  # Starszy chorąży belongs to the postwar warrant corps (1963).
        out[:] = [replace(r, branch='warrant') if r.grade == 6 else r for r in out]
    elif nation == 'china' and service in ('army', 'air'):
        out[:] = [replace(r, branch='warrant', authority=1) if r.grade == 7 else r for r in out]
    elif nation == 'hungary' and service in ('army', 'air'):
        out[:] = [replace(r, branch='officer candidate', authority=1) if r.grade == 7 else r for r in out]
    return tuple(sorted(out, key=lambda r: (r.order, r.key)))


def available(nation, service='army', year=1944):
    return [r for r in catalog(nation, service) if r.since <= year < r.until]


def current(actor):
    return lookup(actor.nation, actor.__dict__.get('service', 'army'), actor.rank, actor.__dict__.get('rank_id'))


@lru_cache(maxsize=2048)
def lookup(nation, service, grade, key):
    ranks = catalog(nation, service)
    selected = next((r for r in ranks if r.key == key and r.grade == grade), None)
    return selected or next((r for r in ranks if r.grade == grade and r.branch == 'line'), None) or \
        next((r for r in ranks if r.grade == grade), None) or \
        next((r for r in ranks if r.title == ladder(nation, service)[max(0,min(18,grade))][0]), None) or \
        max((r for r in ranks if r.grade <= grade), key=lambda r:r.grade, default=None)


def assign(actor, rank):
    actor.rank = rank.grade
    actor.rank_id = rank.key


def choices(actor, year):
    """Next national rank, optional warrant/technical branch, or a commission.

    A commission is explicit; staying enlisted never silently commissions you.
    Equal-grade alternatives are appointments, not an endless source of rewards.
    """
    ranks = available(actor.nation, actor.__dict__.get('service', 'army'), year)
    old = current(actor)
    if old is None:
        return []
    result = []
    branch = old.branch
    same = [r for r in ranks if r.branch == branch and r.order > old.order and
            (r.grade < 8 if old.grade < 8 else r.grade >= 8)]
    if same:
        next_order = min(r.order for r in same)
        result.extend(r for r in same if r.order == next_order)
    if old.grade < 8:
        # British Army warrants continue the senior-soldier career; other
        # warrants are technical appointments with limited line authority.
        if old.grade >= 4 and branch in ('line', 'technical'):
            for br in dict.fromkeys(r.branch for r in ranks if r.branch.startswith('warrant') or r.branch in ('flight', 'officer candidate', "Viceroy's commission")):
                if br == branch:
                    continue
                candidates = [r for r in ranks if r.branch == br and r.order > old.order]
                if candidates:
                    result.append(min(candidates, key=lambda r: r.order))
        if old.grade >= 1 and old.grade < 4 and branch == 'line':
            tech = [r for r in ranks if r.branch == 'technical' and r.grade > old.grade]
            if tech:
                result.append(min(tech, key=lambda r: r.order))
        if branch == 'technical':
            # Taking a line NCO post is an explicit appointment with new duties.
            result.extend(r for r in ranks if r.branch == 'line' and r.grade == old.grade)
        if old.grade >= 3:
            commissioned = [r for r in ranks if r.branch == 'line' and r.grade >= 8]
            if commissioned:
                result.append(min(commissioned, key=lambda r: r.order))
    return list({r.key: r for r in result}.values())
