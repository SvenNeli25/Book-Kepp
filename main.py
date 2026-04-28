from database import get_all_entries, add_entry, delete_entry


VALID_TIPI = ["book", "audiobook"]

VALID_ZVRSTI = [
    "Fantazija",
    "Znanstvena fantastika",
    "Romanca",
    "Kriminalka",
    "Triler",
    "Grozljivka",
    "Avantura",
    "Zgodovinski roman",
    "Mladinski roman",
    "Realisticni roman",
    "Self-Help",
    "Drugo"
]

VALID_TIERJI = ["S", "A", "B", "C", "D", "F"]

VALID_KRITERIJI = [
    "zgodba",
    "liki",
    "tempo",
    "slog",
    "custveni_vpliv",
    "naracija",
    "jasnost_govora",
    "zvocna_izkusnja"
]


def input_choice(label, valid_values, default_value):
    while True:
        print(f"\nMožne vrednosti za {label}:")
        for value in valid_values:
            print(f"- {value}")

        user_input = input(f"{label} [{default_value}]: ").strip()

        if user_input == "":
            return default_value

        if user_input in valid_values:
            return user_input

        print("Napačen vnos. Poskusi še enkrat.")


def input_text(label, default_value=None):
    user_input = input(f"{label}: ").strip()

    if user_input == "":
        return default_value

    return user_input


def input_float(label, default_value):
    while True:
        user_input = input(f"{label} [{default_value}]: ").strip()

        if user_input == "":
            return default_value

        try:
            return float(user_input)
        except ValueError:
            print("Vnesti moraš število.")


def input_int(label, default_value=None):
    while True:
        user_input = input(f"{label}: ").strip()

        if user_input == "":
            return default_value

        try:
            return int(user_input)
        except ValueError:
            print("Vnesti moraš celo število.")


while True:
    print("\n1. Dodaj knjigo")
    print("2. Prikaži knjige")
    print("3. Izbriši knjigo")
    print("4. Izhod")

    choice = input("Izbira: ").strip()

    if choice == "1":
        naslov = input_text("Naslov", "Neznan naslov")
        avtor = input_text("Avtor", "Neznan avtor")

        tip = input_choice("Tip", VALID_TIPI, "book")
        zvrst = input_choice("Zvrst", VALID_ZVRSTI, "Drugo")

        slika_naslovnice = input_text("Slika naslovnice", None)
        kratko_mnenje = input_text("Kratko mnenje", "Brez mnenja")
        fav_quote = input_text("Priljubljeni citat", None)
        opombe = input_text("Opombe", None)

        skupna_ocena = input_float("Skupna ocena", 5.0)
        tier = input_choice("Tier", VALID_TIERJI, "C")

        st_strani = input_int("Število strani", None)
        trajanje_minut = input_int("Trajanje v minutah", None)

        ratings = {}

        while True:
            kriterij = input_choice(
                "Kriterij",
                VALID_KRITERIJI + ["koncaj"],
                "koncaj"
            )

            if kriterij == "koncaj":
                break

            ocena = input_float(f"Ocena za {kriterij}", 5.0)
            ratings[kriterij] = ocena

        add_entry(
            naslov,
            avtor,
            tip,
            zvrst,
            slika_naslovnice,
            kratko_mnenje,
            fav_quote,
            opombe,
            skupna_ocena,
            tier,
            st_strani,
            trajanje_minut,
            ratings
        )

        print("Vnos je bil uspešno dodan.")

    elif choice == "2":
        entries = get_all_entries()

        if not entries:
            print("Trenutno ni nobenega vnosa.")
        else:
            for entry in entries:
                print(entry)

    elif choice == "3":
        entries = get_all_entries()
        if not entries:
            print("Trenutno ni nobenega vnosa za brisanje.")
            continue
        else:
            print("Obstoječi vnosi:")
            for entry in entries:
                print(f"ID: {entry['id']}, Naslov: {entry['naslov']}")
        entry_id = input_int("ID vnosa za brisanje")

        if entry_id is not None:
            delete_entry(entry_id)
            print(f"Vnos z ID {entry_id} je bil izbrisan.")
        else:
            print("Neveljaven ID.")
    
    elif choice == "4":
        print("Izhod iz programa.")
        break
        
    else:
        print("Napačna izbira. Izberi 1, 2, 3 ali 4.")