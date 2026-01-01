from worlds.AutoWorld import World
from BaseClasses import Item, Location, Region, ItemClassification, Entrance
from worlds.generic.Rules import set_rule

class AlchimisteItem(Item):
    game: str = "Alchimiste"

class AlchimisteLocation(Location):
    game: str = "Alchimiste"

class AlchimisteWorld(World):
    game = "Alchimiste"
    topology_present = True
    data_version = 5

    item_name_to_id = {
        "Puce de Mouvement": 60001, "Epee": 60002, "Masque a Gaz": 60003,
        "Potion": 60004, "Puce de Gauche": 60005, "Puce de Recul": 60006,
        "Boussole": 60007, "Clef Etage 1": 60012, "Clef Etage 2": 60008,
        "Clef Etage 3": 60009, "Clef Etage 4": 60010, "Clef Etage 5": 60011,
    }

    # On génère dynamiquement les IDs pour ne pas faire d'erreurs
    location_name_to_id = {
        "Cadeau de l'Alchimiste": 70021,
        **{f"Niveau {i}": 70000 + i for i in range(1, 6)},
        **{f"Coffre {c} Etage {i}": 70005 + ((i-1)*3) + c for i in range(1, 6) for c in range(1, 4)},
        **{f"Ennemi {e} Etage {i}": 70030 + ((i-1)*4) + e for i in range(1, 6) for e in range(1, 5)}
    }

    def create_items(self):
        # 1. Objet de départ (déjà collecté, ne va pas dans le pool)
        self.multiworld.push_precollected(AlchimisteItem("Puce de Mouvement", ItemClassification.progression, 60001, self.player))

        # 2. Créer la liste des objets importants à cacher (10 objets ici)
        pool = []
        
        # Objets de progression
        prog_items = ["Masque a Gaz", "Puce de Gauche", "Puce de Recul", 
                      "Clef Etage 1", "Clef Etage 2", "Clef Etage 3", "Clef Etage 4", "Clef Etage 5"]
        for name in prog_items:
            pool.append(AlchimisteItem(name, ItemClassification.progression, self.item_name_to_id[name], self.player))
        
        # Objets utiles
        for name in ["Epee", "Boussole"]:
            pool.append(AlchimisteItem(name, ItemClassification.useful, self.item_name_to_id[name], self.player))

        # 3. CALCUL DU REMPLISSAGE (Le "Fix" pour le Multiworld)
        # On a 41 locations au total. 
        # La Puce de Mouvement est pre-collected, elle ne compte pas dans les coffres.
        # Il faut donc que Jerome apporte 41 objets pour remplir ses 41 coffres/niveaux.
        
        nombre_total_locations = len(self.location_name_to_id) # C'est 41
        nombre_objets_actuels = len(pool) # C'est 10
        
        potions_a_ajouter = nombre_total_locations - nombre_objets_actuels
        
        for _ in range(potions_a_ajouter):
            pool.append(AlchimisteItem("Potion", ItemClassification.filler, 60004, self.player))

        # 4. On ajoute TOUT ton pool personnel au pool du Multiworld
        self.multiworld.itempool += pool

    def create_regions(self):
        menu = Region("Menu", self.player, self.multiworld)
        menu.locations.append(AlchimisteLocation(self.player, "Cadeau de l'Alchimiste", 70021, menu))
        self.multiworld.regions.append(menu)

        for i in range(1, 6):
            region = Region(f"Etage {i}", self.player, self.multiworld)
            # Coffres
            for c in range(1, 4):
                n = f"Coffre {c} Etage {i}"
                region.locations.append(AlchimisteLocation(self.player, n, self.location_name_to_id[n], region))
            # Ennemis
            for e in range(1, 5):
                n = f"Ennemi {e} Etage {i}"
                region.locations.append(AlchimisteLocation(self.player, n, self.location_name_to_id[n], region))
            # Sortie
            region.locations.append(AlchimisteLocation(self.player, f"Niveau {i}", self.location_name_to_id[f"Niveau {i}"], region))
            self.multiworld.regions.append(region)

        menu.connect(self.multiworld.get_region("Etage 1", self.player), "Entrer dans le Donjon")
        for i in range(1, 5):
            self.multiworld.get_region(f"Etage {i}", self.player).connect(self.multiworld.get_region(f"Etage {i+1}", self.player), f"Vers Etage {i+1}")

    def set_rules(self):
        p = self.player
        set_rule(self.multiworld.get_entrance("Entrer dans le Donjon", p), lambda state: state.has("Puce de Mouvement", p))
        for i in range(1, 6):
            clef = f"Clef Etage {i}"
            for loc in self.multiworld.get_region(f"Etage {i}", p).locations:
                set_rule(loc, lambda state, c=clef: state.has(c, p))
            # Règle spéciale : Pour valider un ennemi SANS MOURIR, il faut l'Épée (optionnel pour la logique, mais propre)
            # Ici on laisse libre pour éviter les softlocks.

        for i in range(1, 5):
            entrance = self.multiworld.get_entrance(f"Vers Etage {i+1}", p)
            if i == 2:
                set_rule(entrance, lambda state: state.can_reach(f"Niveau 2", "Location", p) and state.has("Masque a Gaz", p))
            else:
                set_rule(entrance, lambda state, idx=i: state.can_reach(f"Niveau {idx}", "Location", p))

        self.multiworld.completion_condition[p] = lambda state: state.can_reach("Niveau 5", "Location", p)